# O'zbekcha katalog (lotin, Telegram HTML). Identifikatorlar va o'zgaruvchilar ru va en kataloglariga mos.
# "<id>-neutral" — neytral ohangli chatlar uchun jiddiy variant.

pick-language =
    🌍 <b>1/3 · Til · Язык · Language</b>

    Tilni tanlang · Выберите язык · Choose your language
onboarding-intro =
    👋 <b>Salom, men cpstands!</b>
    Contestlarning jonli natijalari, eslatmalar va do'stlaringiz masala yechganda xabar. Uch qadamda tayyor bo'lamiz.
onboarding-intro-neutral =
    <b>cpstands</b>
    Contest natijalari, eslatmalar va yechilgan masalalar haqida xabarlar. Sozlash uch qadam.
onboarding-pick-timezone =
    🧭 <b>2/3 · Vaqt zonasi</b>

    Quyidan vaqt zonangizni tanlang. Ro'yxatda yo'qmi? Shahar nomini yozing: <code>/timezone Tashkent</code>
setup-done =
    ✅ <b>3/3 · Hammasi tayyor!</b>

    🌍 { $language}
    🧭 { $zone }

    Oxirgi qadam: kimni kuzatishimni ayting.
    <code>/track add tourist, jiangly</code>
setup-done-neutral =
    ✅ <b>3/3 · Sozlash yakunlandi</b>

    🌍 { $language}
    🧭 { $zone }

    Kuzatiladigan handlelarni qo'shing:
    <code>/track add tourist, jiangly</code>
setup-celebrate = 🎉 Xush kelibsiz! Do'stlaringiz natijalari shu yerda chiqadi.
setup-admin-needed = 🔒 Sozlashni faqat chat adminlari yakunlay oladi. Adminga /start yuborishni ayting.
group-added =
    👋 <b>Meni qo'shganingiz uchun rahmat!</b>
    Til va vaqt zonasini tanlash uchun admin /start yuborsin. O'n soniya vaqt oladi.
group-added-neutral =
    <b>cpstands chatga qo'shildi.</b>
    Til va vaqt zonasini tanlash uchun admin /start yuborsin.

timezone-set =
    🧭 Vaqt zonasi o'rnatildi: <b>{ $zone }</b>
    🕐 U yerda hozir <b>{ $time }</b>
timezone-choose = 🧭 “<b>{ $query }</b>” uchun bir nechta variant topildi. Birini tanlang:
timezone-not-found =
    ❌ “<b>{ $query }</b>” uchun vaqt zonasi topilmadi.
    Shahar nomini inglizcha yozing, masalan: <code>/timezone Tashkent</code>
timezone-invalid-button = ❌ Bu vaqt zonasi yaroqsiz. /timezone yuborib, qayta urinib ko'ring.

settings-summary =
    ⚙️ <b>Sozlamalar</b>

    🌍 Til: <b>{ $language }</b>
    🧭 Vaqt zonasi: <b>{ $zone }</b>
    🎭 Ohang: <b>{ $mood ->
        [neutral] neytral
       *[playful] qiziqarli
    }</b>
    🔔 Eslatmalar: <b>{ $reminders ->
        [off] o'chiq
       *[on] yoqilgan
    }</b>
    👥 Kuzatilmoqda: <b>{ $count ->
        [one] { $count } ta handle
       *[other] { $count } ta handle
    }</b>
settings-timezone-unset = hali tanlanmagan
button-language = Til
button-timezone = Vaqt zonasi
button-tone = { $mood ->
        [neutral] Ohang: neytral
       *[playful] Ohang: qiziqarli
    }
button-help-settings = Sozlamalar
button-help-track = Handlelar

track-usage =
    👥 <b>Kuzatiladigan handlelar</b>

    <code>/track add handle1, handle2</code> — qo'shish
    <code>/track remove handle</code> — olib tashlash
    <code>/track list</code> — ro'yxatni ko'rish
track-list-empty = 👥 Ro'yxat bo'sh. Handle qo'shing: <code>/track add tourist, jiangly</code>
track-list-header = { $count ->
        [one] 👥 <b>Kuzatilmoqda: { $count } ta handle</b>
       *[other] 👥 <b>Kuzatilmoqda: { $count } ta handle</b>
    }
track-added = ✅ Qo'shildi: <b>{ $handles }</b>
track-added-neutral = Qo'shildi: { $handles }
track-already = ➖ Allaqachon ro'yxatda: { $handles }
track-unknown = ❌ Codeforces'da topilmadi: { $handles }
track-invalid = ❌ Handle formati noto'g'ri: { $handles }
track-limit = 🔒 Ro'yxat { $limit } ta handle bilan cheklangan. Qo'shilmadi: { $handles }
track-truncated = ⚠️ Bitta xabarda juda ko'p element bor; faqat birinchi { $limit } tasi o'qildi.
track-removed = ✅ Olib tashlandi: <b>{ $handles }</b>
track-not-found = ➖ Ro'yxatda yo'q: { $handles }
track-nothing = Qiladigan ish yo'q. Misol: <code>/track add tourist, jiangly</code>
track-source-error = ⚠️ Codeforces hozir javob bermayapti. Hech narsa o'zgartirilmadi; bir daqiqadan keyin qayta urinib ko'ring.

not-admin = 🔒 Buni faqat chat adminlari qila oladi.
button-expired = Tugma eskirgan. Buyruqni qayta yuboring.
rate-limited = ⏰ Sekinroq, shoshqaloq! Bir zum kuting.
rate-limited-neutral = So'rovlar juda ko'p. Biroz kuting.
error-generic = 😵 Mening tomonimda nimadir buzildi. Birozdan keyin qayta urinib ko'ring.
error-generic-neutral = Xatolik yuz berdi. Keyinroq urinib ko'ring.
coming-soon = 🚧 Bu buyruq hali ustaxonada. Tez orada tayyor bo'ladi!
coming-soon-neutral = Bu buyruq hali mavjud emas.
help-text =
    💬 <b>cpstands</b> — siz va do'stlaringiz uchun contestlar

    <b>Sozlash</b>
    /start — til va vaqt zonasi
    /timezone — vaqt zonasini o'zgartirish
    /settings — joriy sozlamalar

    <b>Do'stlar</b>
    /track — kuzatiladigan handlelar
    /friends — xuddi shu, shaxsiy chatda

    <b>Contestlar</b> <i>(tez orada)</i>
    /standings · /upcoming · /rank

standings-usage =
    🏆 <b>Contest natijalari</b>

    <code>/standings 1970</code> — contest raqami bo'yicha
    <code>/standings https://codeforces.com/contest/1970</code> — havola bo'yicha
standings-status = { $phase ->
        [running] 🔥 <b>Davom etmoqda</b>
        [before] ⏰ <b>Hali boshlanmagan</b>
       *[finished] 🏁 <b>Yakunlangan</b>
    } · 👥 { $count ->
        [one] { $count } ishtirokchi
       *[other] { $count } ishtirokchi
    } · 🕐 { $time }
standings-footer = { $first }–{ $last }-qatorlar, jami { $total } · masalalar { $from_problem }–{ $to_problem }
standings-empty = Hozircha qatorlar yo'q.
standings-not-found = ❌ <b>{ $id }</b> raqamli contest Codeforces'da topilmadi.
standings-not-started = ⏰ <b>{ $name }</b> hali boshlanmagan. Jadval boshlanganda paydo bo'ladi.
standings-source-error = ⚠️ Codeforces hozir javob bermayapti. Bir daqiqadan keyin qayta urinib ko'ring.
button-refresh = Yangilash

reminder =
    ⏰ <b>{ $name }</b>
    { $left ->
        [day] 24 soatdan keyin boshlanadi
        [hour] 1 soatdan keyin boshlanadi
       *[minutes] { $minutes } daqiqadan keyin boshlanadi
    }
    🕐 { $start }
reminder-neutral =
    <b>{ $name }</b>
    { $left ->
        [day] 24 soatdan keyin boshlanadi
        [hour] 1 soatdan keyin boshlanadi
       *[minutes] { $minutes } daqiqadan keyin boshlanadi
    }
    { $start }
reminder-moved =
    🔄 <b>{ $name }</b> vaqti o'zgardi.
    🕐 { $start }
reminder-moved-neutral =
    <b>{ $name }</b> vaqti o'zgardi.
    { $start }
reminder-cancelled = ❌ <b>{ $name }</b> bekor qilindi.
reminder-cancelled-neutral = <b>{ $name }</b> bekor qilindi.
button-register = Ro'yxatdan o'tish
button-contest = Contest sahifasi
button-reminders = { $state ->
        [off] Eslatmalar: o'chiq
       *[on] Eslatmalar: yoqilgan
    }
upcoming-header = 🏆 <b>Yaqin contestlar</b>
upcoming-line =
    { $name }
    🕐 { $start } · ⏱ { $duration }
upcoming-empty = Keyingi ikki hafta uchun contest rejalashtirilmagan.
upcoming-source-error = ⚠️ Codeforces hozir javob bermayapti. Bir daqiqadan keyin qayta urinib ko'ring.
