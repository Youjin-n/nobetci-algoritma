"""
Test exact production request locally.
"""
import json
from collections import defaultdict, Counter

from app.services.scheduler.solver import SchedulerSolver
from app.schemas.schedule import ScheduleRequest

# Read the exact production request
request_json = """{
  "period": {
    "id": "1b6a8def-d3ea-4b2d-ad90-a1b971127331",
    "name": "15 Aralık - 25 Ocak 2026",
    "startDate": "2025-12-15",
    "endDate": "2026-01-25"
  },
  "users": [
    {"id": "c68d5278-ff8e-4406-ae65-129b5f61fd22", "name": "Zeynep Özyürek", "email": "ozyurekz22@itu.edu.tr", "likesNight": false, "dislikesWeekend": false, "history": {"totalAllTime": 0, "expectedTotal": 0, "weekdayCount": 0, "weekendCount": 0, "countAAllTime": 0, "countBAllTime": 0, "countCAllTime": 0, "countNightAllTime": 0, "countWeekendAllTime": 0, "slotTypeCounts": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}}},
    {"id": "610c1482-c211-4250-ba77-49b36e293aa2", "name": "Elif Öner", "email": "onere22@itu.edu.tr", "likesNight": false, "dislikesWeekend": false, "history": {"totalAllTime": 0, "expectedTotal": 0, "weekdayCount": 0, "weekendCount": 0, "countAAllTime": 0, "countBAllTime": 0, "countCAllTime": 0, "countNightAllTime": 0, "countWeekendAllTime": 0, "slotTypeCounts": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}}},
    {"id": "45c14fe7-22b7-4d8c-a6bf-6c028abf9af7", "name": "Enes Yumurtacı", "email": "yumurtacie21@itu.edu.tr", "likesNight": false, "dislikesWeekend": false, "history": {"totalAllTime": 0, "expectedTotal": 0, "weekdayCount": 0, "weekendCount": 0, "countAAllTime": 0, "countBAllTime": 0, "countCAllTime": 0, "countNightAllTime": 0, "countWeekendAllTime": 0, "slotTypeCounts": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}}},
    {"id": "4387666a-c361-4dd8-8e90-d6d6da15b19c", "name": "Melisa Öztürk", "email": "ozturkmel23@itu.edu.tr", "likesNight": false, "dislikesWeekend": false, "history": {"totalAllTime": 0, "expectedTotal": 0, "weekdayCount": 0, "weekendCount": 0, "countAAllTime": 0, "countBAllTime": 0, "countCAllTime": 0, "countNightAllTime": 0, "countWeekendAllTime": 0, "slotTypeCounts": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}}},
    {"id": "a0d44849-de2c-41b8-904e-1448be97420e", "name": "Elif Rabia Nur Kırlı", "email": "kirli22@itu.edu.tr", "likesNight": false, "dislikesWeekend": false, "history": {"totalAllTime": 0, "expectedTotal": 0, "weekdayCount": 0, "weekendCount": 0, "countAAllTime": 0, "countBAllTime": 0, "countCAllTime": 0, "countNightAllTime": 0, "countWeekendAllTime": 0, "slotTypeCounts": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}}},
    {"id": "639bd076-4223-440b-90bc-f482dd3f960f", "name": "Emirhan Baran", "email": "baran21@itu.edu.tr", "likesNight": false, "dislikesWeekend": false, "history": {"totalAllTime": 0, "expectedTotal": 0, "weekdayCount": 0, "weekendCount": 0, "countAAllTime": 0, "countBAllTime": 0, "countCAllTime": 0, "countNightAllTime": 0, "countWeekendAllTime": 0, "slotTypeCounts": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}}},
    {"id": "7efa76db-2374-4edc-bd47-e3b01545a351", "name": "Emirhan Gök", "email": "gokem22@itu.edu.tr", "likesNight": false, "dislikesWeekend": false, "history": {"totalAllTime": 0, "expectedTotal": 0, "weekdayCount": 0, "weekendCount": 0, "countAAllTime": 0, "countBAllTime": 0, "countCAllTime": 0, "countNightAllTime": 0, "countWeekendAllTime": 0, "slotTypeCounts": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}}},
    {"id": "bfdad93d-95af-4190-832c-ed8bb0eac543", "name": "Eylül Gençoğlu", "email": "gencoglue21@itu.edu.tr", "likesNight": false, "dislikesWeekend": false, "history": {"totalAllTime": 0, "expectedTotal": 0, "weekdayCount": 0, "weekendCount": 0, "countAAllTime": 0, "countBAllTime": 0, "countCAllTime": 0, "countNightAllTime": 0, "countWeekendAllTime": 0, "slotTypeCounts": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}}},
    {"id": "1f91a8b6-86db-489c-b24a-f2e3cf0d0c1f", "name": "Fatih Bakır", "email": "bakir22@itu.edu.tr", "likesNight": false, "dislikesWeekend": false, "history": {"totalAllTime": 0, "expectedTotal": 0, "weekdayCount": 0, "weekendCount": 0, "countAAllTime": 0, "countBAllTime": 0, "countCAllTime": 0, "countNightAllTime": 0, "countWeekendAllTime": 0, "slotTypeCounts": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}}},
    {"id": "4d51abf3-b4a0-4be1-a06d-84086a47589e", "name": "Nurullah Özköse", "email": "ozkose22@itu.edu.tr", "likesNight": false, "dislikesWeekend": false, "history": {"totalAllTime": 0, "expectedTotal": 0, "weekdayCount": 0, "weekendCount": 0, "countAAllTime": 0, "countBAllTime": 0, "countCAllTime": 0, "countNightAllTime": 0, "countWeekendAllTime": 0, "slotTypeCounts": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}}},
    {"id": "71db8866-faf5-44fb-80bd-6f0458b87833", "name": "Selin Hayırlı", "email": "hayirli22@itu.edu.tr", "likesNight": false, "dislikesWeekend": false, "history": {"totalAllTime": 0, "expectedTotal": 0, "weekdayCount": 0, "weekendCount": 0, "countAAllTime": 0, "countBAllTime": 0, "countCAllTime": 0, "countNightAllTime": 0, "countWeekendAllTime": 0, "slotTypeCounts": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}}},
    {"id": "ce665b47-eaef-42e9-bc21-ffb338f9d99b", "name": "Ahmet Furkan Ünnü", "email": "unnu24@itu.edu.tr", "likesNight": false, "dislikesWeekend": false, "history": {"totalAllTime": 0, "expectedTotal": 0, "weekdayCount": 0, "weekendCount": 0, "countAAllTime": 0, "countBAllTime": 0, "countCAllTime": 0, "countNightAllTime": 0, "countWeekendAllTime": 0, "slotTypeCounts": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}}},
    {"id": "c96ace83-6177-4e15-a17b-edee4c407f01", "name": "Melih Borhan", "email": "borhan21@itu.edu.tr", "likesNight": false, "dislikesWeekend": false, "history": {"totalAllTime": 0, "expectedTotal": 0, "weekdayCount": 0, "weekendCount": 0, "countAAllTime": 0, "countBAllTime": 0, "countCAllTime": 0, "countNightAllTime": 0, "countWeekendAllTime": 0, "slotTypeCounts": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}}},
    {"id": "efba21cd-9cbc-4274-b45a-8c7541c04a8c", "name": "Ahmet Selim Öztürk", "email": "ozturkahm23@itu.edu.tr", "likesNight": false, "dislikesWeekend": false, "history": {"totalAllTime": 0, "expectedTotal": 0, "weekdayCount": 0, "weekendCount": 0, "countAAllTime": 0, "countBAllTime": 0, "countCAllTime": 0, "countNightAllTime": 0, "countWeekendAllTime": 0, "slotTypeCounts": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}}},
    {"id": "d684d979-c712-4ace-a258-ebf74405e846", "name": "Zeynep Suna Çalık", "email": "calikz23@itu.edu.tr", "likesNight": false, "dislikesWeekend": false, "history": {"totalAllTime": 0, "expectedTotal": 0, "weekdayCount": 0, "weekendCount": 0, "countAAllTime": 0, "countBAllTime": 0, "countCAllTime": 0, "countNightAllTime": 0, "countWeekendAllTime": 0, "slotTypeCounts": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}}},
    {"id": "6e79e5bb-9246-409d-a962-0742e25ad340", "name": "Emirhan Yavuz", "email": "yavuzem23@itu.edu.tr", "likesNight": false, "dislikesWeekend": false, "history": {"totalAllTime": 0, "expectedTotal": 0, "weekdayCount": 0, "weekendCount": 0, "countAAllTime": 0, "countBAllTime": 0, "countCAllTime": 0, "countNightAllTime": 0, "countWeekendAllTime": 0, "slotTypeCounts": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}}},
    {"id": "18718ae2-81c7-48fc-b9c6-f5829a4743d1", "name": "Osman Değirmenci", "email": "degirmencio22@itu.edu.tr", "likesNight": false, "dislikesWeekend": false, "history": {"totalAllTime": 0, "expectedTotal": 0, "weekdayCount": 0, "weekendCount": 0, "countAAllTime": 0, "countBAllTime": 0, "countCAllTime": 0, "countNightAllTime": 0, "countWeekendAllTime": 0, "slotTypeCounts": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}}},
    {"id": "cd7e7e36-c6f5-4716-81f7-9a7e0a507420", "name": "Süleyman Enis Otağ", "email": "otag23@itu.edu.tr", "likesNight": false, "dislikesWeekend": false, "history": {"totalAllTime": 0, "expectedTotal": 0, "weekdayCount": 0, "weekendCount": 0, "countAAllTime": 0, "countBAllTime": 0, "countCAllTime": 0, "countNightAllTime": 0, "countWeekendAllTime": 0, "slotTypeCounts": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}}},
    {"id": "ad448e3e-eef3-4ad4-844e-e20a83950870", "name": "Muhammed Enes Çetin", "email": "cetinmu23@itu.edu.tr", "likesNight": false, "dislikesWeekend": false, "history": {"totalAllTime": 0, "expectedTotal": 0, "weekdayCount": 0, "weekendCount": 0, "countAAllTime": 0, "countBAllTime": 0, "countCAllTime": 0, "countNightAllTime": 0, "countWeekendAllTime": 0, "slotTypeCounts": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}}},
    {"id": "30eb136b-6ba6-4c8c-a762-11e54d3d3124", "name": "Nihal Metin", "email": "metinn23@itu.edu.tr", "likesNight": false, "dislikesWeekend": false, "history": {"totalAllTime": 0, "expectedTotal": 0, "weekdayCount": 0, "weekendCount": 0, "countAAllTime": 0, "countBAllTime": 0, "countCAllTime": 0, "countNightAllTime": 0, "countWeekendAllTime": 0, "slotTypeCounts": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}}},
    {"id": "232371de-cbd1-41ec-9d35-b7d31036af6a", "name": "Ali Cem Noyan", "email": "noyan23@itu.edu.tr", "likesNight": false, "dislikesWeekend": false, "history": {"totalAllTime": 0, "expectedTotal": 0, "weekdayCount": 0, "weekendCount": 0, "countAAllTime": 0, "countBAllTime": 0, "countCAllTime": 0, "countNightAllTime": 0, "countWeekendAllTime": 0, "slotTypeCounts": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}}},
    {"id": "590dc882-f044-4e38-959a-b01d49c0e8aa", "name": "Sıla Sinem Dağdelen", "email": "dagdelen22@itu.edu.tr", "likesNight": false, "dislikesWeekend": false, "history": {"totalAllTime": 0, "expectedTotal": 0, "weekdayCount": 0, "weekendCount": 0, "countAAllTime": 0, "countBAllTime": 0, "countCAllTime": 0, "countNightAllTime": 0, "countWeekendAllTime": 0, "slotTypeCounts": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}}},
    {"id": "762db649-7044-4b8b-bf30-aaff563f5628", "name": "Elif Züleyha Taçyıldız", "email": "tacyildiz22@itu.edu.tr", "likesNight": false, "dislikesWeekend": false, "history": {"totalAllTime": 0, "expectedTotal": 0, "weekdayCount": 0, "weekendCount": 0, "countAAllTime": 0, "countBAllTime": 0, "countCAllTime": 0, "countNightAllTime": 0, "countWeekendAllTime": 0, "slotTypeCounts": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}}},
    {"id": "76ef8dec-69b2-4f7a-ac77-ca70671093f9", "name": "Melih Emre Sönmez", "email": "sonmezme23@itu.edu.tr", "likesNight": false, "dislikesWeekend": false, "history": {"totalAllTime": 0, "expectedTotal": 0, "weekdayCount": 0, "weekendCount": 0, "countAAllTime": 0, "countBAllTime": 0, "countCAllTime": 0, "countNightAllTime": 0, "countWeekendAllTime": 0, "slotTypeCounts": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}}},
    {"id": "c695f032-c0a6-4590-818e-98570761e806", "name": "İbrahim Etem Mermer", "email": "mermer23@itu.edu.tr", "likesNight": false, "dislikesWeekend": false, "history": {"totalAllTime": 0, "expectedTotal": 0, "weekdayCount": 0, "weekendCount": 0, "countAAllTime": 0, "countBAllTime": 0, "countCAllTime": 0, "countNightAllTime": 0, "countWeekendAllTime": 0, "slotTypeCounts": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}}},
    {"id": "1d3e5e69-2b2e-4579-8c0e-dda4e18e1431", "name": "Mustafa Küçükcoşkun", "email": "kucukcoskun21@itu.edu.tr", "likesNight": false, "dislikesWeekend": false, "history": {"totalAllTime": 0, "expectedTotal": 0, "weekdayCount": 0, "weekendCount": 0, "countAAllTime": 0, "countBAllTime": 0, "countCAllTime": 0, "countNightAllTime": 0, "countWeekendAllTime": 0, "slotTypeCounts": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}}}
  ],
  "slots": [
    {"id": "1a68eaae-0a24-4eb9-98be-1a07d2ea5c4c", "date": "2025-12-15", "dutyType": "A", "dayType": "WEEKDAY", "seats": [{"id": "s1", "role": "DESK"}, {"id": "s2", "role": "DESK"}, {"id": "s3", "role": "OPERATOR"}]},
    {"id": "fca6d2a3-9624-4a54-87a7-cfdfe95d877e", "date": "2025-12-15", "dutyType": "B", "dayType": "WEEKDAY", "seats": [{"id": "s4", "role": null}, {"id": "s5", "role": null}]},
    {"id": "139c7038-fd03-4805-9bee-1c439d88fc93", "date": "2025-12-15", "dutyType": "C", "dayType": "WEEKDAY", "seats": [{"id": "s6", "role": null}, {"id": "s7", "role": null}]},
    {"id": "s16", "date": "2025-12-16", "dutyType": "A", "dayType": "WEEKDAY", "seats": [{"id": "s8", "role": "DESK"}, {"id": "s9", "role": "DESK"}, {"id": "s10", "role": "OPERATOR"}]},
    {"id": "s17", "date": "2025-12-16", "dutyType": "B", "dayType": "WEEKDAY", "seats": [{"id": "s11", "role": null}, {"id": "s12", "role": null}]},
    {"id": "s18", "date": "2025-12-16", "dutyType": "C", "dayType": "WEEKDAY", "seats": [{"id": "s13", "role": null}, {"id": "s14", "role": null}]},
    {"id": "s19", "date": "2025-12-17", "dutyType": "A", "dayType": "WEEKDAY", "seats": [{"id": "s15", "role": "DESK"}, {"id": "s16", "role": "DESK"}, {"id": "s17", "role": "OPERATOR"}]},
    {"id": "s20", "date": "2025-12-17", "dutyType": "B", "dayType": "WEEKDAY", "seats": [{"id": "s18", "role": null}, {"id": "s19", "role": null}]},
    {"id": "s21", "date": "2025-12-17", "dutyType": "C", "dayType": "WEEKDAY", "seats": [{"id": "s20", "role": null}, {"id": "s21", "role": null}]},
    {"id": "s22", "date": "2025-12-18", "dutyType": "A", "dayType": "WEEKDAY", "seats": [{"id": "s22", "role": "DESK"}, {"id": "s23", "role": "DESK"}, {"id": "s24", "role": "OPERATOR"}]},
    {"id": "s23", "date": "2025-12-18", "dutyType": "B", "dayType": "WEEKDAY", "seats": [{"id": "s25", "role": null}, {"id": "s26", "role": null}]},
    {"id": "s24", "date": "2025-12-18", "dutyType": "C", "dayType": "WEEKDAY", "seats": [{"id": "s27", "role": null}, {"id": "s28", "role": null}]},
    {"id": "s25", "date": "2025-12-19", "dutyType": "A", "dayType": "WEEKDAY", "seats": [{"id": "s29", "role": "DESK"}, {"id": "s30", "role": "DESK"}, {"id": "s31", "role": "OPERATOR"}]},
    {"id": "s26", "date": "2025-12-19", "dutyType": "B", "dayType": "WEEKDAY", "seats": [{"id": "s32", "role": null}, {"id": "s33", "role": null}]},
    {"id": "s27", "date": "2025-12-19", "dutyType": "C", "dayType": "WEEKDAY", "seats": [{"id": "s34", "role": null}, {"id": "s35", "role": null}]},
    {"id": "s28", "date": "2025-12-20", "dutyType": "D", "dayType": "WEEKEND", "seats": [{"id": "s36", "role": null}, {"id": "s37", "role": null}]},
    {"id": "s29", "date": "2025-12-20", "dutyType": "E", "dayType": "WEEKEND", "seats": [{"id": "s38", "role": null}, {"id": "s39", "role": null}]},
    {"id": "s30", "date": "2025-12-20", "dutyType": "F", "dayType": "WEEKEND", "seats": [{"id": "s40", "role": null}, {"id": "s41", "role": null}]},
    {"id": "s31", "date": "2025-12-21", "dutyType": "D", "dayType": "WEEKEND", "seats": [{"id": "s42", "role": null}, {"id": "s43", "role": null}]},
    {"id": "s32", "date": "2025-12-21", "dutyType": "E", "dayType": "WEEKEND", "seats": [{"id": "s44", "role": null}, {"id": "s45", "role": null}]},
    {"id": "s33", "date": "2025-12-21", "dutyType": "F", "dayType": "WEEKEND", "seats": [{"id": "s46", "role": null}, {"id": "s47", "role": null}]},
    {"id": "s34", "date": "2025-12-22", "dutyType": "A", "dayType": "WEEKDAY", "seats": [{"id": "s48", "role": "DESK"}, {"id": "s49", "role": "DESK"}, {"id": "s50", "role": "OPERATOR"}]},
    {"id": "s35", "date": "2025-12-22", "dutyType": "B", "dayType": "WEEKDAY", "seats": [{"id": "s51", "role": null}, {"id": "s52", "role": null}]},
    {"id": "s36", "date": "2025-12-22", "dutyType": "C", "dayType": "WEEKDAY", "seats": [{"id": "s53", "role": null}, {"id": "s54", "role": null}]},
    {"id": "s37", "date": "2025-12-23", "dutyType": "A", "dayType": "WEEKDAY", "seats": [{"id": "s55", "role": "DESK"}, {"id": "s56", "role": "DESK"}, {"id": "s57", "role": "OPERATOR"}]},
    {"id": "s38", "date": "2025-12-23", "dutyType": "B", "dayType": "WEEKDAY", "seats": [{"id": "s58", "role": null}, {"id": "s59", "role": null}]},
    {"id": "s39", "date": "2025-12-23", "dutyType": "C", "dayType": "WEEKDAY", "seats": [{"id": "s60", "role": null}, {"id": "s61", "role": null}]},
    {"id": "s40", "date": "2025-12-24", "dutyType": "A", "dayType": "WEEKDAY", "seats": [{"id": "s62", "role": "DESK"}, {"id": "s63", "role": "DESK"}, {"id": "s64", "role": "OPERATOR"}]},
    {"id": "s41", "date": "2025-12-24", "dutyType": "B", "dayType": "WEEKDAY", "seats": [{"id": "s65", "role": null}, {"id": "s66", "role": null}]},
    {"id": "s42", "date": "2025-12-24", "dutyType": "C", "dayType": "WEEKDAY", "seats": [{"id": "s67", "role": null}, {"id": "s68", "role": null}]},
    {"id": "s43", "date": "2025-12-25", "dutyType": "A", "dayType": "WEEKDAY", "seats": [{"id": "s69", "role": "DESK"}, {"id": "s70", "role": "DESK"}, {"id": "s71", "role": "OPERATOR"}]},
    {"id": "s44", "date": "2025-12-25", "dutyType": "B", "dayType": "WEEKDAY", "seats": [{"id": "s72", "role": null}, {"id": "s73", "role": null}]},
    {"id": "s45", "date": "2025-12-25", "dutyType": "C", "dayType": "WEEKDAY", "seats": [{"id": "s74", "role": null}, {"id": "s75", "role": null}]},
    {"id": "s46", "date": "2025-12-26", "dutyType": "A", "dayType": "WEEKDAY", "seats": [{"id": "s76", "role": "DESK"}, {"id": "s77", "role": "DESK"}, {"id": "s78", "role": "OPERATOR"}]},
    {"id": "s47", "date": "2025-12-26", "dutyType": "B", "dayType": "WEEKDAY", "seats": [{"id": "s79", "role": null}, {"id": "s80", "role": null}]},
    {"id": "s48", "date": "2025-12-26", "dutyType": "C", "dayType": "WEEKDAY", "seats": [{"id": "s81", "role": null}, {"id": "s82", "role": null}]},
    {"id": "s49", "date": "2025-12-27", "dutyType": "D", "dayType": "WEEKEND", "seats": [{"id": "s83", "role": null}, {"id": "s84", "role": null}]},
    {"id": "s50", "date": "2025-12-27", "dutyType": "E", "dayType": "WEEKEND", "seats": [{"id": "s85", "role": null}, {"id": "s86", "role": null}]},
    {"id": "s51", "date": "2025-12-27", "dutyType": "F", "dayType": "WEEKEND", "seats": [{"id": "s87", "role": null}, {"id": "s88", "role": null}]},
    {"id": "s52", "date": "2025-12-28", "dutyType": "D", "dayType": "WEEKEND", "seats": [{"id": "s89", "role": null}, {"id": "s90", "role": null}]},
    {"id": "s53", "date": "2025-12-28", "dutyType": "E", "dayType": "WEEKEND", "seats": [{"id": "s91", "role": null}, {"id": "s92", "role": null}]},
    {"id": "s54", "date": "2025-12-28", "dutyType": "F", "dayType": "WEEKEND", "seats": [{"id": "s93", "role": null}, {"id": "s94", "role": null}]},
    {"id": "s55", "date": "2025-12-29", "dutyType": "A", "dayType": "WEEKDAY", "seats": [{"id": "s95", "role": "DESK"}, {"id": "s96", "role": "DESK"}, {"id": "s97", "role": "OPERATOR"}]},
    {"id": "s56", "date": "2025-12-29", "dutyType": "B", "dayType": "WEEKDAY", "seats": [{"id": "s98", "role": null}, {"id": "s99", "role": null}]},
    {"id": "s57", "date": "2025-12-29", "dutyType": "C", "dayType": "WEEKDAY", "seats": [{"id": "s100", "role": null}, {"id": "s101", "role": null}]},
    {"id": "s58", "date": "2025-12-30", "dutyType": "A", "dayType": "WEEKDAY", "seats": [{"id": "s102", "role": "DESK"}, {"id": "s103", "role": "DESK"}, {"id": "s104", "role": "OPERATOR"}]},
    {"id": "s59", "date": "2025-12-30", "dutyType": "B", "dayType": "WEEKDAY", "seats": [{"id": "s105", "role": null}, {"id": "s106", "role": null}]},
    {"id": "s60", "date": "2025-12-30", "dutyType": "C", "dayType": "WEEKDAY", "seats": [{"id": "s107", "role": null}, {"id": "s108", "role": null}]},
    {"id": "s61", "date": "2025-12-31", "dutyType": "A", "dayType": "WEEKDAY", "seats": [{"id": "s109", "role": "DESK"}, {"id": "s110", "role": "DESK"}, {"id": "s111", "role": "OPERATOR"}]},
    {"id": "s62", "date": "2025-12-31", "dutyType": "B", "dayType": "WEEKDAY", "seats": [{"id": "s112", "role": null}, {"id": "s113", "role": null}]},
    {"id": "s63", "date": "2025-12-31", "dutyType": "C", "dayType": "WEEKDAY", "seats": [{"id": "s114", "role": null}, {"id": "s115", "role": null}]},
    {"id": "s64", "date": "2026-01-01", "dutyType": "A", "dayType": "WEEKDAY", "seats": [{"id": "s116", "role": "DESK"}, {"id": "s117", "role": "DESK"}, {"id": "s118", "role": "OPERATOR"}]},
    {"id": "s65", "date": "2026-01-01", "dutyType": "B", "dayType": "WEEKDAY", "seats": [{"id": "s119", "role": null}, {"id": "s120", "role": null}]},
    {"id": "s66", "date": "2026-01-01", "dutyType": "C", "dayType": "WEEKDAY", "seats": [{"id": "s121", "role": null}, {"id": "s122", "role": null}]},
    {"id": "s67", "date": "2026-01-02", "dutyType": "A", "dayType": "WEEKDAY", "seats": [{"id": "s123", "role": "DESK"}, {"id": "s124", "role": "DESK"}, {"id": "s125", "role": "OPERATOR"}]},
    {"id": "s68", "date": "2026-01-02", "dutyType": "B", "dayType": "WEEKDAY", "seats": [{"id": "s126", "role": null}, {"id": "s127", "role": null}]},
    {"id": "s69", "date": "2026-01-02", "dutyType": "C", "dayType": "WEEKDAY", "seats": [{"id": "s128", "role": null}, {"id": "s129", "role": null}]},
    {"id": "s70", "date": "2026-01-03", "dutyType": "D", "dayType": "WEEKEND", "seats": [{"id": "s130", "role": null}, {"id": "s131", "role": null}]},
    {"id": "s71", "date": "2026-01-03", "dutyType": "E", "dayType": "WEEKEND", "seats": [{"id": "s132", "role": null}, {"id": "s133", "role": null}]},
    {"id": "s72", "date": "2026-01-03", "dutyType": "F", "dayType": "WEEKEND", "seats": [{"id": "s134", "role": null}, {"id": "s135", "role": null}]},
    {"id": "s73", "date": "2026-01-04", "dutyType": "D", "dayType": "WEEKEND", "seats": [{"id": "s136", "role": null}, {"id": "s137", "role": null}]},
    {"id": "s74", "date": "2026-01-04", "dutyType": "E", "dayType": "WEEKEND", "seats": [{"id": "s138", "role": null}, {"id": "s139", "role": null}]},
    {"id": "s75", "date": "2026-01-04", "dutyType": "F", "dayType": "WEEKEND", "seats": [{"id": "s140", "role": null}, {"id": "s141", "role": null}]},
    {"id": "s76", "date": "2026-01-05", "dutyType": "A", "dayType": "WEEKDAY", "seats": [{"id": "s142", "role": "DESK"}, {"id": "s143", "role": "DESK"}, {"id": "s144", "role": "OPERATOR"}]},
    {"id": "s77", "date": "2026-01-05", "dutyType": "B", "dayType": "WEEKDAY", "seats": [{"id": "s145", "role": null}, {"id": "s146", "role": null}]},
    {"id": "s78", "date": "2026-01-05", "dutyType": "C", "dayType": "WEEKDAY", "seats": [{"id": "s147", "role": null}, {"id": "s148", "role": null}]},
    {"id": "s79", "date": "2026-01-06", "dutyType": "A", "dayType": "WEEKDAY", "seats": [{"id": "s149", "role": "DESK"}, {"id": "s150", "role": "DESK"}, {"id": "s151", "role": "OPERATOR"}]},
    {"id": "s80", "date": "2026-01-06", "dutyType": "B", "dayType": "WEEKDAY", "seats": [{"id": "s152", "role": null}, {"id": "s153", "role": null}]},
    {"id": "s81", "date": "2026-01-06", "dutyType": "C", "dayType": "WEEKDAY", "seats": [{"id": "s154", "role": null}, {"id": "s155", "role": null}]},
    {"id": "s82", "date": "2026-01-07", "dutyType": "A", "dayType": "WEEKDAY", "seats": [{"id": "s156", "role": "DESK"}, {"id": "s157", "role": "DESK"}, {"id": "s158", "role": "OPERATOR"}]},
    {"id": "s83", "date": "2026-01-07", "dutyType": "B", "dayType": "WEEKDAY", "seats": [{"id": "s159", "role": null}, {"id": "s160", "role": null}]},
    {"id": "s84", "date": "2026-01-07", "dutyType": "C", "dayType": "WEEKDAY", "seats": [{"id": "s161", "role": null}, {"id": "s162", "role": null}]},
    {"id": "s85", "date": "2026-01-08", "dutyType": "A", "dayType": "WEEKDAY", "seats": [{"id": "s163", "role": "DESK"}, {"id": "s164", "role": "DESK"}, {"id": "s165", "role": "OPERATOR"}]},
    {"id": "s86", "date": "2026-01-08", "dutyType": "B", "dayType": "WEEKDAY", "seats": [{"id": "s166", "role": null}, {"id": "s167", "role": null}]},
    {"id": "s87", "date": "2026-01-08", "dutyType": "C", "dayType": "WEEKDAY", "seats": [{"id": "s168", "role": null}, {"id": "s169", "role": null}]},
    {"id": "s88", "date": "2026-01-09", "dutyType": "A", "dayType": "WEEKDAY", "seats": [{"id": "s170", "role": "DESK"}, {"id": "s171", "role": "DESK"}, {"id": "s172", "role": "OPERATOR"}]},
    {"id": "s89", "date": "2026-01-09", "dutyType": "B", "dayType": "WEEKDAY", "seats": [{"id": "s173", "role": null}, {"id": "s174", "role": null}]},
    {"id": "s90", "date": "2026-01-09", "dutyType": "C", "dayType": "WEEKDAY", "seats": [{"id": "s175", "role": null}, {"id": "s176", "role": null}]},
    {"id": "s91", "date": "2026-01-10", "dutyType": "D", "dayType": "WEEKEND", "seats": [{"id": "s177", "role": null}, {"id": "s178", "role": null}]},
    {"id": "s92", "date": "2026-01-10", "dutyType": "E", "dayType": "WEEKEND", "seats": [{"id": "s179", "role": null}, {"id": "s180", "role": null}]},
    {"id": "s93", "date": "2026-01-10", "dutyType": "F", "dayType": "WEEKEND", "seats": [{"id": "s181", "role": null}, {"id": "s182", "role": null}]},
    {"id": "s94", "date": "2026-01-11", "dutyType": "D", "dayType": "WEEKEND", "seats": [{"id": "s183", "role": null}, {"id": "s184", "role": null}]},
    {"id": "s95", "date": "2026-01-11", "dutyType": "E", "dayType": "WEEKEND", "seats": [{"id": "s185", "role": null}, {"id": "s186", "role": null}]},
    {"id": "s96", "date": "2026-01-11", "dutyType": "F", "dayType": "WEEKEND", "seats": [{"id": "s187", "role": null}, {"id": "s188", "role": null}]},
    {"id": "s97", "date": "2026-01-12", "dutyType": "A", "dayType": "WEEKDAY", "seats": [{"id": "s189", "role": "DESK"}, {"id": "s190", "role": "DESK"}, {"id": "s191", "role": "OPERATOR"}]},
    {"id": "s98", "date": "2026-01-12", "dutyType": "B", "dayType": "WEEKDAY", "seats": [{"id": "s192", "role": null}, {"id": "s193", "role": null}]},
    {"id": "s99", "date": "2026-01-12", "dutyType": "C", "dayType": "WEEKDAY", "seats": [{"id": "s194", "role": null}, {"id": "s195", "role": null}]},
    {"id": "s100", "date": "2026-01-13", "dutyType": "A", "dayType": "WEEKDAY", "seats": [{"id": "s196", "role": "DESK"}, {"id": "s197", "role": "DESK"}, {"id": "s198", "role": "OPERATOR"}]},
    {"id": "s101", "date": "2026-01-13", "dutyType": "B", "dayType": "WEEKDAY", "seats": [{"id": "s199", "role": null}, {"id": "s200", "role": null}]},
    {"id": "s102", "date": "2026-01-13", "dutyType": "C", "dayType": "WEEKDAY", "seats": [{"id": "s201", "role": null}, {"id": "s202", "role": null}]},
    {"id": "s103", "date": "2026-01-14", "dutyType": "A", "dayType": "WEEKDAY", "seats": [{"id": "s203", "role": "DESK"}, {"id": "s204", "role": "DESK"}, {"id": "s205", "role": "OPERATOR"}]},
    {"id": "s104", "date": "2026-01-14", "dutyType": "B", "dayType": "WEEKDAY", "seats": [{"id": "s206", "role": null}, {"id": "s207", "role": null}]},
    {"id": "s105", "date": "2026-01-14", "dutyType": "C", "dayType": "WEEKDAY", "seats": [{"id": "s208", "role": null}, {"id": "s209", "role": null}]},
    {"id": "s106", "date": "2026-01-15", "dutyType": "A", "dayType": "WEEKDAY", "seats": [{"id": "s210", "role": "DESK"}, {"id": "s211", "role": "DESK"}, {"id": "s212", "role": "OPERATOR"}]},
    {"id": "s107", "date": "2026-01-15", "dutyType": "B", "dayType": "WEEKDAY", "seats": [{"id": "s213", "role": null}, {"id": "s214", "role": null}]},
    {"id": "s108", "date": "2026-01-15", "dutyType": "C", "dayType": "WEEKDAY", "seats": [{"id": "s215", "role": null}, {"id": "s216", "role": null}]},
    {"id": "s109", "date": "2026-01-16", "dutyType": "A", "dayType": "WEEKDAY", "seats": [{"id": "s217", "role": "DESK"}, {"id": "s218", "role": "DESK"}, {"id": "s219", "role": "OPERATOR"}]},
    {"id": "s110", "date": "2026-01-16", "dutyType": "B", "dayType": "WEEKDAY", "seats": [{"id": "s220", "role": null}, {"id": "s221", "role": null}]},
    {"id": "s111", "date": "2026-01-16", "dutyType": "C", "dayType": "WEEKDAY", "seats": [{"id": "s222", "role": null}, {"id": "s223", "role": null}]},
    {"id": "s112", "date": "2026-01-17", "dutyType": "D", "dayType": "WEEKEND", "seats": [{"id": "s224", "role": null}, {"id": "s225", "role": null}]},
    {"id": "s113", "date": "2026-01-17", "dutyType": "E", "dayType": "WEEKEND", "seats": [{"id": "s226", "role": null}, {"id": "s227", "role": null}]},
    {"id": "s114", "date": "2026-01-17", "dutyType": "F", "dayType": "WEEKEND", "seats": [{"id": "s228", "role": null}, {"id": "s229", "role": null}]},
    {"id": "s115", "date": "2026-01-18", "dutyType": "D", "dayType": "WEEKEND", "seats": [{"id": "s230", "role": null}, {"id": "s231", "role": null}]},
    {"id": "s116", "date": "2026-01-18", "dutyType": "E", "dayType": "WEEKEND", "seats": [{"id": "s232", "role": null}, {"id": "s233", "role": null}]},
    {"id": "s117", "date": "2026-01-18", "dutyType": "F", "dayType": "WEEKEND", "seats": [{"id": "s234", "role": null}, {"id": "s235", "role": null}]},
    {"id": "s118", "date": "2026-01-19", "dutyType": "A", "dayType": "WEEKDAY", "seats": [{"id": "s236", "role": "DESK"}, {"id": "s237", "role": "DESK"}, {"id": "s238", "role": "OPERATOR"}]},
    {"id": "s119", "date": "2026-01-19", "dutyType": "B", "dayType": "WEEKDAY", "seats": [{"id": "s239", "role": null}, {"id": "s240", "role": null}]},
    {"id": "s120", "date": "2026-01-19", "dutyType": "C", "dayType": "WEEKDAY", "seats": [{"id": "s241", "role": null}, {"id": "s242", "role": null}]},
    {"id": "s121", "date": "2026-01-20", "dutyType": "A", "dayType": "WEEKDAY", "seats": [{"id": "s243", "role": "DESK"}, {"id": "s244", "role": "DESK"}, {"id": "s245", "role": "OPERATOR"}]},
    {"id": "s122", "date": "2026-01-20", "dutyType": "B", "dayType": "WEEKDAY", "seats": [{"id": "s246", "role": null}, {"id": "s247", "role": null}]},
    {"id": "s123", "date": "2026-01-20", "dutyType": "C", "dayType": "WEEKDAY", "seats": [{"id": "s248", "role": null}, {"id": "s249", "role": null}]},
    {"id": "s124", "date": "2026-01-21", "dutyType": "A", "dayType": "WEEKDAY", "seats": [{"id": "s250", "role": "DESK"}, {"id": "s251", "role": "DESK"}, {"id": "s252", "role": "OPERATOR"}]},
    {"id": "s125", "date": "2026-01-21", "dutyType": "B", "dayType": "WEEKDAY", "seats": [{"id": "s253", "role": null}, {"id": "s254", "role": null}]},
    {"id": "s126", "date": "2026-01-21", "dutyType": "C", "dayType": "WEEKDAY", "seats": [{"id": "s255", "role": null}, {"id": "s256", "role": null}]},
    {"id": "s127", "date": "2026-01-22", "dutyType": "A", "dayType": "WEEKDAY", "seats": [{"id": "s257", "role": "DESK"}, {"id": "s258", "role": "DESK"}, {"id": "s259", "role": "OPERATOR"}]},
    {"id": "s128", "date": "2026-01-22", "dutyType": "B", "dayType": "WEEKDAY", "seats": [{"id": "s260", "role": null}, {"id": "s261", "role": null}]},
    {"id": "s129", "date": "2026-01-22", "dutyType": "C", "dayType": "WEEKDAY", "seats": [{"id": "s262", "role": null}, {"id": "s263", "role": null}]},
    {"id": "s130", "date": "2026-01-23", "dutyType": "A", "dayType": "WEEKDAY", "seats": [{"id": "s264", "role": "DESK"}, {"id": "s265", "role": "DESK"}, {"id": "s266", "role": "OPERATOR"}]},
    {"id": "s131", "date": "2026-01-23", "dutyType": "B", "dayType": "WEEKDAY", "seats": [{"id": "s267", "role": null}, {"id": "s268", "role": null}]},
    {"id": "s132", "date": "2026-01-23", "dutyType": "C", "dayType": "WEEKDAY", "seats": [{"id": "s269", "role": null}, {"id": "s270", "role": null}]},
    {"id": "s133", "date": "2026-01-24", "dutyType": "D", "dayType": "WEEKEND", "seats": [{"id": "s271", "role": null}, {"id": "s272", "role": null}]},
    {"id": "s134", "date": "2026-01-24", "dutyType": "E", "dayType": "WEEKEND", "seats": [{"id": "s273", "role": null}, {"id": "s274", "role": null}]},
    {"id": "s135", "date": "2026-01-24", "dutyType": "F", "dayType": "WEEKEND", "seats": [{"id": "s275", "role": null}, {"id": "s276", "role": null}]},
    {"id": "s136", "date": "2026-01-25", "dutyType": "D", "dayType": "WEEKEND", "seats": [{"id": "s277", "role": null}, {"id": "s278", "role": null}]},
    {"id": "s137", "date": "2026-01-25", "dutyType": "E", "dayType": "WEEKEND", "seats": [{"id": "s279", "role": null}, {"id": "s280", "role": null}]},
    {"id": "s138", "date": "2026-01-25", "dutyType": "F", "dayType": "WEEKEND", "seats": [{"id": "s281", "role": null}, {"id": "s282", "role": null}]}
  ],
  "unavailability": []
}"""

data = json.loads(request_json)
request = ScheduleRequest(**data)

print("=" * 80)
print("PRODUCTION REQUEST LOCAL TESTİ")
print("=" * 80)
print(f"Kullanıcı: {len(request.users)}")
print(f"Slot: {len(request.slots)}")
total_seats = sum(len(s.seats) for s in request.slots)
print(f"Toplam koltuk: {total_seats}")
print(f"Kişi başı ideal: {total_seats / len(request.users):.2f}")

solver = SchedulerSolver()
response = solver.solve(request)

print(f"\nMeta: Status={response.meta.solverStatus}, Min={response.meta.minShifts}, Max={response.meta.maxShifts}")
print(f"Fark: {response.meta.maxShifts - response.meta.minShifts}")

# Analyze
user_stats = defaultdict(lambda: {'total': 0, 'A': 0, 'B': 0, 'C': 0, 'D': 0, 'E': 0, 'F': 0})
for a in response.assignments:
    # Find slot duty type
    slot = next((s for s in request.slots if s.id == a.slotId), None)
    if slot:
        dtype = slot.dutyType.value if hasattr(slot.dutyType, 'value') else slot.dutyType
        user_stats[a.userId]['total'] += 1
        user_stats[a.userId][dtype] += 1

print(f"\n{'İsim':<25} {'Tot':<4} {'A':<3} {'B':<3} {'C':<3} {'D':<3} {'E':<3} {'F':<3}")
print("-" * 55)
for uid in sorted(user_stats.keys()):
    s = user_stats[uid]
    name = next((u.name for u in request.users if u.id == uid), uid[:8])[:24]
    print(f"{name:<25} {s['total']:<4} {s['A']:<3} {s['B']:<3} {s['C']:<3} {s['D']:<3} {s['E']:<3} {s['F']:<3}")

# Summary
print("\n" + "=" * 80)
print("ÖZET")
print("=" * 80)
totals = [s['total'] for s in user_stats.values()]
a_counts = [s['A'] for s in user_stats.values()]
b_counts = [s['B'] for s in user_stats.values()]
c_counts = [s['C'] for s in user_stats.values()]
weekend = [s['D']+s['E']+s['F'] for s in user_stats.values()]

print(f"TOPLAM: min={min(totals)}, max={max(totals)}, fark={max(totals)-min(totals)} → {dict(Counter(totals))}")
print(f"A: min={min(a_counts)}, max={max(a_counts)}, fark={max(a_counts)-min(a_counts)} → {dict(Counter(a_counts))}")
print(f"B: min={min(b_counts)}, max={max(b_counts)}, fark={max(b_counts)-min(b_counts)} → {dict(Counter(b_counts))}")
print(f"C: min={min(c_counts)}, max={max(c_counts)}, fark={max(c_counts)-min(c_counts)} → {dict(Counter(c_counts))}")
print(f"Weekend: min={min(weekend)}, max={max(weekend)}, fark={max(weekend)-min(weekend)} → {dict(Counter(weekend))}")
