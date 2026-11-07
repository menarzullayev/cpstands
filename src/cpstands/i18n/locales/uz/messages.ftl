# O'zbekcha katalog (lotin). Identifikatorlar va o'zgaruvchilar ru va en kataloglariga mos bo'lishi kerak (testlar tekshiradi).

pick-language = Tilni tanlang · Выберите язык · Choose your language
onboarding-intro = Salom! Men cpstands botiman: contestlarning jonli natijalari, eslatmalar va do'stlaringiz yechgan masalalar haqida xabar beraman.
onboarding-pick-timezone = Vaqt zonangizni tanlang. Ro'yxatda yo'q bo'lsa, shahar nomini inglizcha yozing: /timezone Tashkent
setup-done = Tayyor! Til: { $language }, vaqt zonasi: { $zone }. Endi kuzatiladigan handlelarni qo'shing: /track add tourist, jiangly
setup-admin-needed = Sozlashni faqat chat adminlari yakunlay oladi. Adminga /start yuborishni ayting.
group-added = Meni qo'shganingiz uchun rahmat! Til va vaqt zonasini tanlash uchun admin /start yuborsin.

timezone-set = Vaqt zonasi o'rnatildi: { $zone } (u yerda hozir { $time })
timezone-choose = “{ $query }” uchun bir nechta variant topildi. Birini tanlang:
timezone-not-found = “{ $query }” uchun vaqt zonasi topilmadi. Shahar nomini inglizcha yozing, masalan: /timezone Tashkent
timezone-invalid-button = Bu vaqt zonasi yaroqsiz. /timezone yuborib, qayta urinib ko'ring.

settings-summary =
    Sozlamalar
    Til: { $language }
    Vaqt zonasi: { $zone }
    Kuzatilmoqda: { $count ->
        [one] { $count } ta handle
       *[other] { $count } ta handle
    }
settings-timezone-unset = hali tanlanmagan
button-language = Til
button-timezone = Vaqt zonasi

track-usage =
    Kuzatiladigan handlelar:
    /track add handle1, handle2 - qo'shish
    /track remove handle - olib tashlash
    /track list - ro'yxatni ko'rish
track-list-empty = Ro'yxat bo'sh. Handle qo'shing: /track add tourist, jiangly
track-list-header = { $count ->
        [one] Kuzatilmoqda: { $count } ta handle
       *[other] Kuzatilmoqda: { $count } ta handle
    }
track-added = Qo'shildi: { $handles }
track-already = Allaqachon ro'yxatda: { $handles }
track-unknown = Codeforces'da topilmadi: { $handles }
track-invalid = Handle formati noto'g'ri: { $handles }
track-limit = Ro'yxat { $limit } ta handle bilan cheklangan. Qo'shilmadi: { $handles }
track-truncated = Bitta xabarda juda ko'p element bor; faqat birinchi { $limit } tasi o'qildi.
track-removed = Olib tashlandi: { $handles }
track-not-found = Ro'yxatda yo'q: { $handles }
track-nothing = Qiladigan ish yo'q. Misol: /track add tourist, jiangly
track-source-error = Codeforces hozir javob bermayapti. Hech narsa o'zgartirilmadi; bir daqiqadan keyin qayta urinib ko'ring.

not-admin = Buni faqat chat adminlari qila oladi.
button-expired = Tugma eskirgan. Buyruqni qayta yuboring.
rate-limited = So'rovlar juda ko'p. Biroz kuting.
error-generic = Mening tomonimda xatolik yuz berdi. Keyinroq urinib ko'ring.
coming-soon = Bu buyruq hali mavjud emas. Tez orada qo'shiladi.
help-text =
    Men siz va do'stlaringiz uchun contestlarni kuzataman.
    /start - til va vaqt zonasini sozlash
    /track - kuzatiladigan handlelar
    /timezone - vaqt zonasini o'zgartirish
    /settings - joriy sozlamalar
    /help - shu xabar
