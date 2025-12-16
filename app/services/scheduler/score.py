"""
Penalty/Score Functions for Scheduler

Soft constraint penalty hesaplamaları (Level 0-5).
Toplam penalty minimize edilecek.

Ağırlık Seviyeleri:
- Level 0: Değişmez sert kısıtlar (asla esnetilmez)
- Level 1: ~100,000 (base+2 aşımı, base-1 altı, 0 nöbet, unavailability, 3 gün üst üste)
- Level 2: ~10,000 / 7,000 (şu an boş - Level 1'e taşındı)
- Level 3: ~1,000 - 50,000 (fairness)
- Level 4: ~100 (konfor)
- Level 5: ~10 (tercihler)
"""

from collections import defaultdict
from datetime import date, timedelta
from typing import TYPE_CHECKING

from .constraints import get_week_index, is_night_duty, is_weekend_duty

if TYPE_CHECKING:
    from ortools.sat.python import cp_model

    from app.core.config import Settings

    from .models import InternalSlot, InternalUser, SchedulerContext


class PenaltyBuilder:
    """
    Soft constraint penalty'lerini OR-Tools objective'ine ekleyen builder.
    Toplam penalty minimize edilir.
    """

    def __init__(
        self,
        model: "cp_model.CpModel",
        context: "SchedulerContext",
        x: dict[tuple[int, int], "cp_model.IntVar"],
        settings: "Settings",
    ):
        self.model = model
        self.ctx = context
        self.x = x
        self.settings = settings
        self.penalty_terms: list["cp_model.LinearExpr"] = []

    def add_penalty(self, expr: "cp_model.LinearExpr", weight: int) -> None:
        """Penalty term ekle (negatif weight = bonus)"""
        if weight != 0:
            self.penalty_terms.append(expr * weight)

    def build_all_penalties(
        self,
        user_shift_counts: dict[int, "cp_model.IntVar"],
    ) -> None:
        """Tüm penalty'leri ekle.

        Level 0 (değişmez sert kısıtlar) solver tarafında zaten zorunlu:
        - Her slot requiredCount kadar dolmak zorunda
        - Aynı slotta aynı kişi bir kez yazılabilir
        - Günde max 2 nöbet (ABC/DEF üçlüsü otomatik engellenir)
        Bu kısıtlar asla esnetilmez.

        Level 1 (penalty tabanlı, EN ağır):
        - Unavailability: 200k - EN ağır soft kural
        - ideal±2 sapması: 120-140k
        - 0 nöbet: 80k
        
        Level 2: 3 gün üst üste (7k)
        Level 3: Fairness (history 3k, type 1k)
        Level 4: Konfor (100)
        Level 5: Tercihler (10)
        """
        # Her kullanıcı için ideal_current hesapla
        ideal_current = self._compute_ideal_current()
        
        # Level 1: En ağır soft kural - Unavailability
        self._add_unavailability_penalty()  # 200k - EN AĞIR (çok kapatan = düşük ceza)
        
        # Level 2: Ardışık gün kuralı
        self._add_consecutive_days_penalty()  # 7k

        # Level 3: MinMax Fairness (YENİ SİSTEM)
        self._add_total_minmax_penalty(user_shift_counts)  # 50k - Toplam eşitlik
        self._add_duty_type_fairness_penalty()  # 30k - A/B/C/Weekend ayrı ayrı
        self._add_weekend_slot_fairness_penalty()  # 20k - D/E/F ayrı ayrı
        self._add_night_fairness_penalty()  # 10k - C+F toplam
        
        # Level 4: Soft fairness
        self._add_ideal_soft_penalty(user_shift_counts, ideal_current)  # 4k - |diff|==1 için
        self._add_history_fairness_penalty(user_shift_counts, ideal_current)  # 3k

        # Level 5: Tie-breakers (500 each)
        self._add_weekly_clustering_penalty()  # 500
        self._add_consecutive_nights_penalty()  # 500
        self._add_two_shifts_same_day_penalty()  # 500

        # Level 6: Tercihler

        self._add_preference_penalties()  # 10, 5

    def _compute_ideal_current(self) -> dict[int, int]:
        """
        Her kullanıcı için ideal_current hesapla.
        
        Formül:
            fark_long = totalAllTime - expectedTotal
            ideal_current = base - fark_long
        
        Sınırlama: [max(0, base-2), base+2]
        
        Yeni giren: totalAllTime=0, expectedTotal=0 → fark=0 → ideal=base
        
        Edge case: base=0 iken ideal=0 (küçük slot senaryoları)
        """
        base = self.ctx.base_shifts
        ideal_current: dict[int, int] = {}
        
        for user in self.ctx.users:
            # Uzun vadeli fark
            fark_long = user.history_total - user.history_expected
            
            # İdeal = base - fark
            ideal_float = base - fark_long
            
            # Sınırla: [max(0, base-2), base+2]
            # base=0 iken min_ideal=0 olur, conflict yaratmaz
            min_ideal = max(0, base - 2)
            max_ideal = base + 2
            ideal = max(min_ideal, min(max_ideal, round(ideal_float)))
            
            ideal_current[user.index] = ideal
        
        return ideal_current

    def _add_total_minmax_penalty(
        self,
        user_shift_counts: dict[int, "cp_model.IntVar"],
    ) -> None:
        """
        Level 3: Total MinMax Fairness.
        
        Tüm kullanıcıların toplam nöbet sayısı arasındaki farkı minimize et.
        penalty = (max_total - min_total) * weight
        
        Bu garantili tight distribution sağlar.
        """
        weight = self.settings.penalty_total_minmax  # 50k
        num_users = len(self.ctx.users)

        if num_users < 2:
            return

        max_possible = len(self.ctx.slots)
        
        # max_val ve min_val değişkenleri
        max_val = self.model.NewIntVar(0, max_possible, "max_total")
        min_val = self.model.NewIntVar(0, max_possible, "min_total")

        # Her kullanıcı için: max_val >= count, min_val <= count
        for user in self.ctx.users:
            count_var = user_shift_counts[user.index]
            self.model.Add(max_val >= count_var)
            self.model.Add(min_val <= count_var)

        # Fark = max - min
        diff = self.model.NewIntVar(0, max_possible, "total_range")
        self.model.Add(diff == max_val - min_val)

        # Penalty: fark * weight
        self.add_penalty(diff, weight)

    def _add_ideal_soft_penalty(
        self,
        user_shift_counts: dict[int, "cp_model.IntVar"],
        ideal_current: dict[int, int],
    ) -> None:
        """
        Level 3.5: Kişi bazında ideal sapma cezası.
        
        Her kullanıcı için |current - ideal| kadar ceza.
        MinMax global eşitliği sağlar, bu fonksiyon bireysel ince ayar yapar.
        
        MinMax + Per-user birlikte:
        - MinMax: max-min farkını 1'e zorlar
        - Per-user: herkesi ideale yaklaştırır
        """
        weight = self.settings.penalty_ideal_soft  # 4k
        max_possible = len(self.ctx.slots)

        for user in self.ctx.users:
            count_var = user_shift_counts[user.index]
            ideal = ideal_current[user.index]

            # diff = count - ideal
            diff = self.model.NewIntVar(-max_possible, max_possible, f"diff_soft_{user.index}")
            self.model.Add(diff == count_var - ideal)

            # abs_diff = |diff| - HER SAPMA İÇİN CEZA
            abs_diff = self.model.NewIntVar(0, max_possible, f"absdiff_soft_{user.index}")
            self.model.AddAbsEquality(abs_diff, diff)

            # Her birim sapma için weight ceza
            self.add_penalty(abs_diff, weight)

    def _add_zero_shifts_penalty(
        self,
        user_shift_counts: dict[int, "cp_model.IntVar"],
    ) -> None:
        """
        Level 1 (80,000): 0 nöbet kalma cezası.
        
        Kimse bu dönem 0 nöbet kalmamalı.
        totalShifts == 0 ise ceza uygulanır.
        """
        weight = self.settings.penalty_zero_shifts

        for user in self.ctx.users:
            count_var = user_shift_counts[user.index]

            # is_zero = 1 iff count_var == 0
            is_zero = self.model.NewBoolVar(f"is_zero_{user.index}")
            
            # is_zero == 1 iff count_var == 0
            # Using: is_zero == 1 => count_var == 0
            #        is_zero == 0 => count_var >= 1
            self.model.Add(count_var == 0).OnlyEnforceIf(is_zero)
            self.model.Add(count_var >= 1).OnlyEnforceIf(is_zero.Not())

            self.add_penalty(is_zero, weight)

    def _add_unavailability_penalty(self) -> None:
        """
        Level 1 (200,000): Unavailability ihlali - EN AĞIR SOFT KURAL.
        Kullanıcı "müsait değilim" dediği slota atanırsa çok ağır ceza.
        
        Bu ceza, tarihsel denge ve base sapmalarından bile daha ağır.
        Solver, tarihsel adalet için "müsait değilim"i feda etmemeli.
        
        FAIRNESS TIE-BREAKER (1,000):
        "Herkes kapattıysa en çok kapatanı yerleştir" kuralı.
        Eğer bir slota tüm kullanıcılar kapalıysa ve solver zorunda kalırsa,
        o kategoride en çok slot kapatan kullanıcıya atama yapılsın.
        
        VIOLATION COUNT (25,000):
        Dönem içi ihlal sayısına göre ek ceza.
        - 1. ihlal: base ceza
        - 2. ihlal: base + 25k
        - 3. ihlal: base + 50k
        Böylece aynı kişiye sürekli abanmak yerine ihlaller dağıtılır.
        
        Categories: A, B, C, Weekend (D+E+F combined)
        """
        base_weight = self.settings.penalty_unavailability  # 200,000
        fairness_weight = self.settings.penalty_unavailability_fairness  # 1,000
        violation_weight = self.settings.penalty_unavailability_violation  # 25,000

        def _get_category(duty_type: str) -> str:
            """DutyType'ı kategoriye çevir (D/E/F -> Weekend)"""
            if duty_type in ("D", "E", "F"):
                return "Weekend"
            return duty_type  # A, B, C as-is

        # Per-user violation count IntVars oluştur
        num_users = len(self.ctx.users)
        max_violations = len(self.ctx.slots)  # Teorik maximum
        
        user_violation_counts: dict[int, "cp_model.IntVar"] = {}
        
        for user in self.ctx.users:
            # Bu kullanıcının unavailable olduğu slotlar
            unavail_slots = [
                slot_idx for (u_idx, slot_idx) in self.ctx.unavailability_set
                if u_idx == user.index
            ]
            
            if not unavail_slots:
                # Bu kullanıcının hiç unavailability'si yok
                user_violation_counts[user.index] = self.model.NewConstant(0)
            else:
                # violation_count = sum of x[user, slot] for unavailable slots
                vcount = self.model.NewIntVar(0, len(unavail_slots), f"viol_cnt_{user.index}")
                viol_vars = [self.x[user.index, s_idx] for s_idx in unavail_slots]
                self.model.Add(vcount == sum(viol_vars))
                user_violation_counts[user.index] = vcount

        # Her unavailability için penalty ekle
        for user_idx, slot_idx in self.ctx.unavailability_set:
            slot = self.ctx.slots[slot_idx]
            category = _get_category(slot.duty_type)
            
            # ÖNCELİK 1: Bu KATEGORİDE en çok kapatan ilk atanır
            # C slotu için → en çok C kapatan ilk
            user_cat_blocked = self.ctx.blocked_count_per_category.get(user_idx, {}).get(category, 0)
            max_cat_blocked = self.ctx.max_blocked_per_category.get(category, 0)
            
            # ÖNCELİK 2 (TIE-BREAKER): TOPLAM slot kapama
            user_total_blocked = self.ctx.total_blocked_count.get(user_idx, 0)
            max_total = self.ctx.max_total_blocked
            
            # Kategori bazlı ceza (ana)
            # Çok kapatan = düşük ceza → zor slotlara atanır
            cat_extra = (max_cat_blocked - user_cat_blocked) * fairness_weight
            
            # Total bazlı ceza (tie-breaker) - daha düşük ağırlık
            # Kategori eşitlerse, total'e bakılır
            total_extra = (max_total - user_total_blocked) * (fairness_weight // 10)
            
            # Toplam extra = kategori + total tie-breaker
            extra_fairness = cat_extra + total_extra
            
            # Sabit kısım: base + fairness extra
            fixed_weight = base_weight + extra_fairness
            
            # Bu atama yapılmışsa sabit ceza
            self.add_penalty(self.x[user_idx, slot_idx], fixed_weight)
            
            # Violation count'a dayalı ek ceza:
            # violation_count * violation_weight * x[user, slot]
            # Ama CP-SAT'ta çarpım zor, basitleştirelim:
            # Eğer bu slot atanırsa, VE user'ın başka violation'ları da varsa extra ceza
            # Yaklaşım: violation_count * violation_weight ifadesini objective'e ekle
            # Ama bu tüm violation'lar için eklenir, sadece bu slot için değil
            # 
            # Daha basit yaklaşım: 
            # Her violation için (violation_count - 1) * violation_weight / N ekle
            # Yani ilk violation serbest, 2. ve sonrası için penalty
            # 
            # En basit: violation_count toplamını penalty olarak ekle (yukarıda zaten hesapladık)
            pass  # Violation count aşağıda ayrıca ekleniyor

        # Her kullanıcı için violation_count^2 veya violation_count * weight
        # Daha basit: Her kullanıcı için, violation_count > 1 ise ekstra ceza
        # violation_count * (violation_count - 1) / 2 * weight ≈ n(n-1)/2 penalty
        # 
        # CP-SAT'ta basitçe: (violation_count - 1)+ * weight
        # excess = max(0, violation_count - 1) → 2. violation'dan itibaren penalty
        for user in self.ctx.users:
            vcount = user_violation_counts[user.index]
            
            # excess = max(0, violation_count - 1)
            # Bu, 2., 3., 4. violation için penalty verir
            excess = self.model.NewIntVar(0, len(self.ctx.slots), f"viol_excess_{user.index}")
            diff = self.model.NewIntVar(-1, len(self.ctx.slots), f"viol_diff_{user.index}")
            self.model.Add(diff == vcount - 1)
            self.model.AddMaxEquality(excess, [diff, self.model.NewConstant(0)])
            
            # excess * violation_weight penalty
            self.add_penalty(excess, violation_weight)

    def _add_total_shift_fairness_penalty(
        self,
        user_shift_counts: dict[int, "cp_model.IntVar"],
    ) -> None:
        """
        Level 3 (1,000): Toplam nöbet sayısı dengelemesi.
        Bu dönemde herkes mümkün olduğunca eşit sayıda nöbet alsın.
        """
        weight = self.settings.penalty_fairness_duty_type
        num_users = len(self.ctx.users)

        if num_users < 2:
            return

        # ideal = total_seats / N
        total_seats = self.ctx.total_seats
        ideal = total_seats // num_users

        for user in self.ctx.users:
            count_var = user_shift_counts[user.index]

            # excess = max(0, count - ideal)
            max_possible = len(self.ctx.slots)
            excess = self.model.NewIntVar(0, max_possible, f"shift_excess_{user.index}")
            diff = self.model.NewIntVar(-max_possible, max_possible, f"shift_diff_{user.index}")
            self.model.Add(diff == count_var - ideal)
            self.model.AddMaxEquality(excess, [diff, self.model.NewConstant(0)])

            self.add_penalty(excess, weight)

    def _add_history_fairness_penalty(
        self,
        user_shift_counts: dict[int, "cp_model.IntVar"],
        ideal_current: dict[int, int],
    ) -> None:
        """
        Level 3 (3,000): Tarihsel denge - İNCE AYAR.
        
        ideal_current zaten expectedTotal bazlı hesaplanıyor.
        Bu ceza sadece hafif bir smoothing sağlar.
        
        ÖNEMLİ: Bu ceza müsaitlik (200k) ve base sapması (120-140k) cezalarından
        ÇOK daha hafif. Solver, tarihsel adaleti sağlamak için müsaitliği
        veya base'i ihlal ETMEZ.
        
        NOT: ideal_current hesabı _compute_ideal_current'de yapılıyor.
        """
        weight = self.settings.penalty_history_fairness  # 3k
        num_users = len(self.ctx.users)

        if num_users < 2:
            return
        
        for user in self.ctx.users:
            count_var = user_shift_counts[user.index]
            ideal = ideal_current[user.index]
            
            # Penalty: idealden her sapma için hafif ceza
            max_possible = len(self.ctx.slots)
            
            # diff = count - ideal
            diff = self.model.NewIntVar(-max_possible, max_possible, f"hist_diff_{user.index}")
            self.model.Add(diff == count_var - ideal)
            
            # abs_diff = |diff|
            abs_diff = self.model.NewIntVar(0, max_possible, f"hist_abs_{user.index}")
            self.model.AddAbsEquality(abs_diff, diff)
            
            self.add_penalty(abs_diff, weight)

    def _add_consecutive_days_penalty(self) -> None:
        """
        Level 2 (7,000): 3 gün üst üste AYNI TÜR nöbet cezası.
        
        Aynı nöbet türünü 3 gün arka arkaya tutmak cezalandırılır:
        - 3 gün A-A-A: ceza
        - 3 gün B-B-B: ceza
        - 3 gün C-C-C: ceza
        - 3 gün D-D-D: ceza
        - 3 gün E-E-E: ceza
        - 3 gün F-F-F: ceza
        
        FARKLI türler arka arkaya gelmesi sorun değil (A-B-C gibi).
        """
        weight = self.settings.penalty_consecutive_days
        sorted_dates = sorted(self.ctx.date_to_slot_indices.keys())
        
        if len(sorted_dates) < 3:
            return
        
        # Her nöbet türü için ayrı kontrol
        duty_types = ["A", "B", "C", "D", "E", "F"]
        
        for duty_type in duty_types:
            # Bu türün slotlarını tarihe göre grupla
            type_slots_by_date: dict[date, list[int]] = {}
            for d, slot_indices in self.ctx.date_to_slot_indices.items():
                type_slots = [
                    s_idx for s_idx in slot_indices
                    if self.ctx.slots[s_idx].duty_type == duty_type
                ]
                if type_slots:
                    type_slots_by_date[d] = type_slots
            
            if not type_slots_by_date:
                continue
            
            for user in self.ctx.users:
                # Her kullanıcı için bu türde günlük "nöbet var mı" değişkenleri
                day_has_type: dict[date, "cp_model.IntVar"] = {}
                
                for d in sorted_dates:
                    if d in type_slots_by_date:
                        day_var = self.model.NewBoolVar(f"day_{duty_type}_{user.index}_{d}")
                        type_slots = [self.x[user.index, s_idx] for s_idx in type_slots_by_date[d]]
                        self.model.AddMaxEquality(day_var, type_slots)
                        day_has_type[d] = day_var
                    else:
                        # Bu türde slot yok → 0
                        day_has_type[d] = self.model.NewConstant(0)
                
                # Her 3'lü ardışık gün penceresi kontrol et
                for i in range(len(sorted_dates) - 2):
                    d1, d2, d3 = sorted_dates[i], sorted_dates[i + 1], sorted_dates[i + 2]
                    
                    # Ardışık mı?
                    if (d2 - d1).days != 1 or (d3 - d2).days != 1:
                        continue
                    
                    # 3 gün de bu türde nöbet varsa ceza
                    all_three = self.model.NewBoolVar(f"consec3_{duty_type}_{user.index}_{i}")
                    self.model.AddMinEquality(all_three, [
                        day_has_type[d1],
                        day_has_type[d2],
                        day_has_type[d3],
                    ])
                    self.add_penalty(all_three, weight)

    def _add_duty_type_fairness_penalty(self) -> None:
        """
        Level 3: A/B/C/Weekend fairness - SİMETRİK PENALTY.
        
        Her tür için idealden SAPMAYI cezalandır (hem fazla hem eksik).
        abs_diff = |count - ideal| kullanarak simetrik ceza.
        
        Bu, MinMax yaklaşımına yakın bir etki sağlar:
        - Birisi fazla alırsa → ceza
        - Birisi az alırsa → ceza
        - Sonuç: Herkes ideale yakın kalır (fark max 1)
        """
        weight = self.settings.penalty_fairness_duty_type
        num_users = len(self.ctx.users)

        if num_users == 0:
            return

        # Her duty type grubu için slot sayısı
        type_slots: dict[str, list["InternalSlot"]] = {
            "A": [],
            "B": [],
            "C": [],
            "WEEKEND": [],
        }

        for slot in self.ctx.slots:
            if slot.duty_type == "A":
                type_slots["A"].append(slot)
            elif slot.duty_type == "B":
                type_slots["B"].append(slot)
            elif slot.duty_type == "C":
                type_slots["C"].append(slot)

            if is_weekend_duty(slot.duty_type):
                type_slots["WEEKEND"].append(slot)

        for type_name, slots in type_slots.items():
            if not slots:
                continue

            total_seats = sum(s.required_count for s in slots)
            
            # Her kullanıcının bu tip için count değişkeni
            user_counts: dict[int, "cp_model.IntVar"] = {}
            for user in self.ctx.users:
                count_var = self.model.NewIntVar(
                    0, total_seats, f"typecount_{type_name}_{user.index}"
                )
                slot_vars = [self.x[user.index, s.index] for s in slots]
                self.model.Add(count_var == sum(slot_vars))
                user_counts[user.index] = count_var

            # MinMax: max ve min değişkenleri
            max_val = self.model.NewIntVar(0, total_seats, f"max_{type_name}")
            min_val = self.model.NewIntVar(0, total_seats, f"min_{type_name}")

            for user in self.ctx.users:
                self.model.Add(max_val >= user_counts[user.index])
                self.model.Add(min_val <= user_counts[user.index])

            # Fark = max - min
            diff = self.model.NewIntVar(0, total_seats, f"range_{type_name}")
            self.model.Add(diff == max_val - min_val)

            # Penalty: fark * weight
            self.add_penalty(diff, weight)

    def _add_night_fairness_penalty(self) -> None:
        """
        Level 5: Night (C+F) MinMax Fairness.
        
        Tüm kullanıcıların gece (C+F) nöbet sayısı arasındaki farkı minimize et.
        """
        weight = self.settings.penalty_fairness_night  # 10k
        num_users = len(self.ctx.users)

        if num_users < 2:
            return

        night_slots = [s for s in self.ctx.slots if is_night_duty(s.duty_type)]
        if not night_slots:
            return

        total_night_seats = sum(s.required_count for s in night_slots)

        # Her kullanıcının night count değişkeni
        user_counts: dict[int, "cp_model.IntVar"] = {}
        for user in self.ctx.users:
            count_var = self.model.NewIntVar(
                0, total_night_seats, f"nightcount_{user.index}"
            )
            night_vars = [self.x[user.index, s.index] for s in night_slots]
            self.model.Add(count_var == sum(night_vars))
            user_counts[user.index] = count_var

        # MinMax
        max_val = self.model.NewIntVar(0, total_night_seats, "max_night")
        min_val = self.model.NewIntVar(0, total_night_seats, "min_night")

        for user in self.ctx.users:
            self.model.Add(max_val >= user_counts[user.index])
            self.model.Add(min_val <= user_counts[user.index])

        diff = self.model.NewIntVar(0, total_night_seats, "range_night")
        self.model.Add(diff == max_val - min_val)
        self.add_penalty(diff, weight)

    def _add_weekend_slot_fairness_penalty(self) -> None:
        """
        Level 4: D/E/F MinMax Fairness.
        
        Her weekend slot tipi (D, E, F) için ayrı ayrı MinMax.
        """
        weight = self.settings.penalty_fairness_weekend_slots  # 20k
        num_users = len(self.ctx.users)

        if num_users < 2:
            return

        weekend_types = ["D", "E", "F"]
        
        for duty_type in weekend_types:
            type_slots = [s for s in self.ctx.slots if s.duty_type == duty_type]
            if not type_slots:
                continue

            total_seats = sum(s.required_count for s in type_slots)
            
            # Her kullanıcının count değişkeni
            user_counts: dict[int, "cp_model.IntVar"] = {}
            for user in self.ctx.users:
                count_var = self.model.NewIntVar(
                    0, total_seats, f"wkndcount_{duty_type}_{user.index}"
                )
                slot_vars = [self.x[user.index, s.index] for s in type_slots]
                self.model.Add(count_var == sum(slot_vars))
                user_counts[user.index] = count_var

            # MinMax
            max_val = self.model.NewIntVar(0, total_seats, f"max_{duty_type}")
            min_val = self.model.NewIntVar(0, total_seats, f"min_{duty_type}")

            for user in self.ctx.users:
                self.model.Add(max_val >= user_counts[user.index])
                self.model.Add(min_val <= user_counts[user.index])

            diff = self.model.NewIntVar(0, total_seats, f"range_{duty_type}")
            self.model.Add(diff == max_val - min_val)
            self.add_penalty(diff, weight)

    def _add_weekly_clustering_penalty(self) -> None:
        """
        Level 4 (100): Haftalık yığılma.
        Haftada 2'den fazla nöbet varsa ceza.
        penalty = 100 * (weekShifts - 2) for weekShifts > 2
        """
        weight = self.settings.penalty_weekly_clustering

        if not self.ctx.slots:
            return

        # Haftaları belirle
        sorted_dates = sorted(self.ctx.date_to_slot_indices.keys())
        if not sorted_dates:
            return

        start_date = sorted_dates[0]

        # Hafta bazında slotları grupla
        week_slots: dict[int, list[int]] = defaultdict(list)
        for slot in self.ctx.slots:
            week_idx = get_week_index(slot.date, start_date)
            week_slots[week_idx].append(slot.index)

        for user in self.ctx.users:
            for week_idx, slot_indices in week_slots.items():
                if len(slot_indices) < 3:
                    # Maximum 2 nöbet mümkün, ceza yok
                    continue

                # Bu haftadaki toplam
                week_count = self.model.NewIntVar(
                    0, len(slot_indices), f"week_{week_idx}_{user.index}"
                )
                week_vars = [self.x[user.index, s_idx] for s_idx in slot_indices]
                self.model.Add(week_count == sum(week_vars))

                # excess = max(0, count - 2)
                excess = self.model.NewIntVar(
                    0, len(slot_indices), f"week_excess_{week_idx}_{user.index}"
                )
                diff = self.model.NewIntVar(
                    -2, len(slot_indices), f"week_diff_{week_idx}_{user.index}"
                )
                self.model.Add(diff == week_count - 2)
                self.model.AddMaxEquality(excess, [diff, self.model.NewConstant(0)])

                self.add_penalty(excess, weight)

    def _add_consecutive_nights_penalty(self) -> None:
        """
        Level 4 (100): Arka arkaya gece nöbetleri.
        Day D ve D+1'de ikisi de C/F ise ceza.
        """
        weight = self.settings.penalty_consecutive_nights
        sorted_dates = sorted(self.ctx.date_to_slot_indices.keys())

        for user in self.ctx.users:
            for i in range(len(sorted_dates) - 1):
                d1, d2 = sorted_dates[i], sorted_dates[i + 1]

                # Ardışık mı?
                if (d2 - d1).days != 1:
                    continue

                # d1'deki gece slotları
                night_slots_d1 = [
                    s_idx for s_idx in self.ctx.date_to_slot_indices[d1]
                    if is_night_duty(self.ctx.slots[s_idx].duty_type)
                ]
                # d2'deki gece slotları
                night_slots_d2 = [
                    s_idx for s_idx in self.ctx.date_to_slot_indices[d2]
                    if is_night_duty(self.ctx.slots[s_idx].duty_type)
                ]

                if not night_slots_d1 or not night_slots_d2:
                    continue

                # d1'de gece var mı
                has_night_d1 = self.model.NewBoolVar(f"night_d1_{user.index}_{i}")
                self.model.AddMaxEquality(
                    has_night_d1,
                    [self.x[user.index, s_idx] for s_idx in night_slots_d1]
                )

                # d2'de gece var mı
                has_night_d2 = self.model.NewBoolVar(f"night_d2_{user.index}_{i}")
                self.model.AddMaxEquality(
                    has_night_d2,
                    [self.x[user.index, s_idx] for s_idx in night_slots_d2]
                )

                # İkisi de varsa ceza
                both_nights = self.model.NewBoolVar(f"both_nights_{user.index}_{i}")
                self.model.AddMinEquality(both_nights, [has_night_d1, has_night_d2])

                self.add_penalty(both_nights, weight)

    def _add_two_shifts_same_day_penalty(self) -> None:
        """
        Level 4 (100): Aynı gün 2 nöbet tutma cezası (konfor).
        
        Hard constraint ile zaten günde max 2 nöbet.
        Burada 2 nöbet tutmayı hafif cezalandırıyoruz.
        Böylece solver mümkünse farklı günlere dağıtmayı tercih eder.
        
        NOT: A+B veya B+C gibi kombinasyonları YASAKLAMAZ,
        sadece mümkünse farklı günlere dağıtmayı teşvik eder.
        """
        weight = self.settings.penalty_two_shifts_same_day  # 100

        for current_date, slot_indices in self.ctx.date_to_slot_indices.items():
            if len(slot_indices) < 2:
                # Tek slot varsa 2 nöbet mümkün değil
                continue

            for user in self.ctx.users:
                day_vars = [self.x[user.index, si] for si in slot_indices]
                
                # day_count = bu gündeki toplam nöbet sayısı
                day_count = self.model.NewIntVar(0, len(day_vars), f"day_cnt_{user.index}_{current_date}")
                self.model.Add(day_count == sum(day_vars))

                # is_two = day_count == 2
                is_two = self.model.NewBoolVar(f"is_two_{user.index}_{current_date}")
                self.model.Add(day_count == 2).OnlyEnforceIf(is_two)
                self.model.Add(day_count != 2).OnlyEnforceIf(is_two.Not())

                self.add_penalty(is_two, weight)

    def _add_preference_penalties(self) -> None:
        """
        Level 5 (10/-5): Kullanıcı tercihleri.
        dislikesWeekend → weekend verince +10
        likesNight → night verince -5 (bonus)
        """
        penalty_weekend = self.settings.penalty_dislikes_weekend
        bonus_night = self.settings.bonus_likes_night

        weekend_slots = [s for s in self.ctx.slots if is_weekend_duty(s.duty_type)]
        night_slots = [s for s in self.ctx.slots if is_night_duty(s.duty_type)]

        for user in self.ctx.users:
            # dislikesWeekend
            if user.dislikes_weekend and weekend_slots:
                for slot in weekend_slots:
                    self.add_penalty(self.x[user.index, slot.index], penalty_weekend)

            # likesNight (bonus = negatif penalty)
            if user.likes_night and night_slots:
                for slot in night_slots:
                    self.add_penalty(self.x[user.index, slot.index], -bonus_night)

    def get_total_objective(self) -> "cp_model.LinearExpr":
        """Toplam penalty'yi döndür (minimize edilecek)"""
        if not self.penalty_terms:
            return self.model.NewConstant(0)
        return sum(self.penalty_terms)


def calculate_desk_operator_distribution(count: int) -> tuple[int, int]:
    """
    A nöbeti için kişi sayısına göre desk/operator dağılımı.

    K=1 → 0 desk, 1 operator
    K=2 → 1 desk, 1 operator
    K=3 → 1 desk, 2 operator
    K=4 → 2 desk, 2 operator
    K=5 → 3 desk, 2 operator
    K=6 → 3 desk, 3 operator
    K=7 → 4 desk, 3 operator

    Returns: (desk_count, operator_count)
    """
    if count <= 0:
        return (0, 0)
    if count == 1:
        return (0, 1)
    if count == 2:
        return (1, 1)

    distribution = {
        3: (1, 2),
        4: (2, 2),
        5: (3, 2),
        6: (3, 3),
        7: (4, 3),
    }

    if count in distribution:
        return distribution[count]

    # K > 7 için genel formül
    desk = (count + 1) // 2
    operator = count - desk
    return (desk, operator)
