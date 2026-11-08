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
    🔔 Eslatmalar: <b>{ $reminders }</b>
    🔥 Alertlar: <b>{ $level ->
        [0] o'chiq
        [1] faqat jadval
        [2] + system testlar
        [3] + upsolve
       *[4] hammasi
    }</b>
    📊 Jadval ustunlari: <b>{ $cols }</b>
    🏁 Xulosa: <b>{ $summary ->
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
help-text =
    💬 <b>cpstands</b> — siz va do'stlaringiz uchun contestlar

    <b>Sozlash</b>
    /start — til va vaqt zonasi
    /timezone — vaqt zonasini o'zgartirish
    /settings — joriy sozlamalar

    <b>Do'stlar</b>
    /track — kuzatiladigan handlelar
    /friends — xuddi shu, shaxsiy chatda
    /rank — kuzatilgan handlelar reytingi
    /rating — bitta foydalanuvchi reyting kartasi
    /summary — kuzatilgan handlelarning oxirgi contestdagi natijasi

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
    }{ $view ->
        [friends]  (do'stlar)
       *[all] {""}
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
        [d3] 3 kundan keyin boshlanadi
        [day] 24 soatdan keyin boshlanadi
        [h2] 2 soatdan keyin boshlanadi
        [hour] 1 soatdan keyin boshlanadi
       *[minutes] { $minutes } daqiqadan keyin boshlanadi
    }
    🕐 { $start }
reminder-neutral =
    <b>{ $name }</b>
    { $left ->
        [d3] 3 kundan keyin boshlanadi
        [day] 24 soatdan keyin boshlanadi
        [h2] 2 soatdan keyin boshlanadi
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
upcoming-header = 🏆 <b>Yaqin contestlar</b>
upcoming-line =
    { $name }
    🕐 { $start } · ⏱ { $duration }
upcoming-empty = Keyingi ikki hafta uchun contest rejalashtirilmagan.
upcoming-source-error = ⚠️ Codeforces hozir javob bermayapti. Bir daqiqadan keyin qayta urinib ko'ring.

alert-contest = 🏆 <b>{ $contest }</b>
alert-solve = { $v ->
        [0] 🔥 { $handle } { $problem } masalasini yechdi · { $title } · ⏱ { $time }
        [1] ⚡ { $handle } { $problem } ni oldi · { $title } · ⏱ { $time }
       *[2] 🎯 { $handle } { $problem } ni uddaladi · { $title } · ⏱ { $time }
    }
alert-solve-neutral = { $v ->
       *[other] { $handle } { $problem } masalasini yechdi ({ $title }), { $time }.
    }
alert-systest-fail = { $v ->
        [0] 💥 { $handle } ning { $problem } yechimi system testdan o'tmadi. Eng yaxshilarda ham bo'ladi! { $title } { $time }
        [1] 🧪 System testlar { $handle } ning { $problem } yechimini qabul qilmadi. Keyingisida omad! { $title } { $time }
       *[2] 😬 { $handle } ning { $problem } yechimi system testda yiqildi. Ruhni tushirmang! { $title } { $time }
    }
alert-systest-fail-neutral = { $v ->
       *[other] System test o'tilmadi: { $handle }, { $problem } masalasi ({ $title }, { $time }).
    }

privacy-text =
    🔒 <b>Maxfiylik</b>

    Men faqat ishlash uchun zarur narsani saqlayman:
    • shu chatning id si, til, vaqt zonasi, ohang va sozlamalar
    • siz kuzatadigan ommaviy Codeforces handlelari
    • o'sha handlelarning contest natijalari, 30 kun

    Xabar matnini saqlamayman va hech qachon parol, API kalit yoki token so'ramayman.
    Shu chat haqida saqlangan hamma narsani o'chirish uchun /delete yuboring.
button-privacy-policy = Siyosat
button-delete-data = Ma'lumotni o'chirish
button-delete-yes = Ha, hammasini o'chir
button-delete-no = Bekor qilish
delete-confirm =
    🗑 <b>Shu chatning barcha ma'lumoti o'chirilsinmi?</b>

    Kuzatilayotgan handlelar, sozlamalar, eslatmalar va jonli jadvallar o'chadi. Buni qaytarib bo'lmaydi.
delete-done =
    ✅ Tayyor. Shu chat haqida saqlangan hamma narsa o'chirildi ({ $handles ->
        [one] { $handles } ta kuzatilgan handle
       *[other] { $handles } ta kuzatilgan handle
    }). Chatdagi xabarlar qoladi, ularni o'zingiz o'chiring. Qayta sozlash uchun /start yuboring.
delete-cancelled = Bekor qilindi. Hech narsa o'chirilmadi.
delete-nothing = Shu chat haqida hech narsa saqlanmagan.
delete-expired = ⏰ Tasdiq eskirgan. /delete ni qayta yuboring.
owner-only = 🔒 Faqat egasi uchun.
owner-status =
    📟 <b>Holat</b> v{ $version } · ishlamoqda { $uptime }

    <b>Manbalar</b>
    { $sources }

    <b>Navbatlar</b>
    kutilayotgan alertlar { $alerts } · kechikkan eslatmalar { $overdue }, rejalashtirilgan { $scheduled }
    jonli xabarlar { $live } · davom etayotgan contestlar { $contests }

    <b>Chatlar</b> { $chats }
    <b>Ochiq operator ogohlantirishlari</b> { $open }
owner-stats =
    📊 <b>Statistika</b>

    Faol chatlar: { $chats }
    Kuzatilgan handlelar: { $handles }
    Yechim hodisalari (24 soat): { $events }
    Yuborilgan eslatmalar (24 soat): { $reminders }
    Navbatdagi alertlar: { $pending } · muvaffaqiyatsiz (24 soat): { $failed }
owner-pause-usage = Manba uchun /pause yoki /resume ni argumentsiz, chat uchun id bilan ishlating.
owner-paused-source = ⏸ <code>{ $source }</code> manbasi to'xtatildi.
owner-resumed-source = ▶️ <code>{ $source }</code> manbasi ishlayapti.
owner-paused-chat = ⏸ <code>{ $id }</code> chati to'xtatildi.
owner-resumed-chat = ▶️ <code>{ $id }</code> chati ishlayapti.
owner-chat-unknown = <code>{ $id }</code> chati kerakli holatda topilmadi.
ops-alert-stale = ⚠️ { $contest } contest jadvali { $age } soniya eskirgan.
ops-alert-late = ⚠️ { $count } ta eslatma bir daqiqadan ko'proq kechikdi.
ops-alert-sends = ⚠️ Oxirgi { $count } yuborishning { $percent }% i muvaffaqiyatsiz.
ops-alert-source = ⚠️ <code>{ $source }</code> manbasi ketma-ket { $count } marta xato berdi.
ops-alert-resolved = ✅ Bartaraf etildi: { $rule }

rank-title = 🏆 Do'stlar reytingi
rank-status = { $count ->
        [one] 👥 { $count } ta handle
       *[other] 👥 { $count } ta handle
    } · 🕐 { $time }
rank-footer = { $first }–{ $last }-qatorlar, jami { $total }
rank-unknown = ❌ Codeforces'da topilmadi: { $handles }
rank-empty = 👥 Ro'yxat bo'sh. Avval handle qo'shing: <code>/track add tourist, jiangly</code>
rank-source-error = ⚠️ Codeforces hozir javob bermayapti. Bir daqiqadan keyin qayta urinib ko'ring.

word-off = o'chiq
button-back = Orqaga
button-columns = Ustunlar: { $n }
button-summary = { $state ->
        [off] Xulosa: o'chiq
       *[on] Xulosa: yoqilgan
    }
button-reminders-menu = Eslatmalar
button-alerts-menu = Alertlar
button-friends = Do'stlar
button-level = { $level ->
        [0] O'chiq
        [1] Jadval
        [2] + System test
        [3] + Upsolve
       *[4] Hammasi
    }
reminders-menu =
    🔔 <b>Eslatmalar</b>

    Contest boshlanishidan oldin qachon eslatishimni tanlang. Vaqtni yoqish yoki o'chirish uchun ustiga bosing.
alerts-menu =
    🔥 <b>Alertlar</b>

    Kuzatilayotgan handlelar haqida qanchalik xabar beray?
    <b>O'chiq</b> — hech narsa
    <b>Jadval</b> — faqat natijalar jadvalida ko'rinadi
    <b>+ System test</b> — yechim system testdan o'tmaganda ham
    <b>+ Upsolve</b> — contestdan keyin yechilgan masalalar ham
    <b>Hammasi</b> — va contest vaqtidagi har bir yechim
friends-menu =
    { $count ->
        [one] 👥 <b>Do'stlar</b> · { $count } ta handle
       *[other] 👥 <b>Do'stlar</b> · { $count } ta handle
    }

    Nima haqida xabar berishimni tanlash uchun handle ustiga bosing.
friends-empty = 👥 Hali handle yo'q. Qo'shing: <code>/track add tourist, jiangly</code>
friend-detail =
    👤 <b>{ $handle }</b>

    Shu handle haqida nima haqida xabar berishimni tanlang.
button-toggle-show = Jadvalda ko'rsatish
button-toggle-solve = Contest vaqtidagi yechimlar
button-toggle-systest = System testdan yiqilish
button-toggle-upsolve = Upsolve
standings-no-friends = 👥 Kuzatilayotgan handlelardan hech biri bu contestda qatnashmagan.
button-view-friends = Do'stlar
button-view-all = Hamma

rating-usage =
    👤 <b>Reyting kartasi</b>

    <code>/rating tourist</code> — foydalanuvchining reytingi, unvoni va oxirgi contesti
rating-not-found = ❌ Codeforces'da <b>{ $handle }</b> nomli foydalanuvchi yo'q.
rating-source-error = ⚠️ Codeforces hozir javob bermayapti. Bir daqiqadan keyin qayta urinib ko'ring.
rating-card =
    👤 <b>{ $handle }</b>

    { $body }
rating-unrated = 🏆 Reytingsiz
rating-line = 🏆 <b>{ $rating }</b> · max { $max } · { $rank }
rating-contests = { $count ->
        [one] 📊 { $count } ta reytingli contest
       *[other] 📊 { $count } ta reytingli contest
    }
rating-no-contests = 📊 Hali reytingli contest yo'q
rating-last = 🕐 Oxirgisi: <b>{ $contest }</b> · { $delta } ({ $old } → { $new })
rating-follow-done = ✅ Ro'yxatga qo'shildi
rating-follow-limit = 🔒 Ro'yxat to'lgan ({ $limit } ta handle).
button-follow = Kuzatish
button-profile = Profil

summary-header = 🏁 <b>{ $contest }</b> yakunlandi · { $count } ta ishtirokchi
summary-line = { $medal } { $handle } · { $rank }-o'rin · { $solved } ta masala
summary-rating = {" "}· { $delta } → { $new }
summary-best = 📈 Reytingda eng katta o'sish: { $handle } ({ $delta })
summary-more = … va yana { $count } ta kuzatilgan handle
summary-unrated = ℹ️ Bu contest uchun reyting o'zgarishi e'lon qilinmagan (hozircha).
summary-usage =
    🏁 <b>Contest xulosasi</b>

    <code>/summary</code> — oxirgi yakunlangan contest
    <code>/summary 2287</code> — raqami bo'yicha contest
summary-no-friends = 👥 Avval handle qo'shing: <code>/track add tourist</code>.
summary-none = 🤷 Kuzatilgan handlelardan hech biri unda qatnashmagan.
summary-source-error = ⚠️ Codeforces hozir javob bermayapti. Bir daqiqadan keyin qayta urinib ko'ring.
button-results = Natijalar
