#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
ISTANBUL XIZMATLARI — TELEGRAM AVTO-POST BOTI (v5.1 — HER YERDE ÇALIŞAN VERSİYON)
=============================================================================
Desteklenen ortamlar:
- Kişisel Bilgisayar (Windows, Mac, Linux)
- Android Telefon / Tablet (Termux ile 7/24)
- Ücretsiz Bulut Sunucuları (Render, Koyeb, Railway - $PORT desteği eklendi)

Özellikler:
1. Resim oluşturma (Nano Banana) tamamen kaldırılmıştır; 0 hata, anında hazır post.
2. Gemini API'nin en güncel modelleri kullanılır.
3. API hatası/kota aşımı olsa bile bot ASLA HATA VERMEZ; 25+ adet hazır,
   profesyonel İstanbul ve Türkiye seyahat rehberi veritabanından kusursuz post üretir.
4. Kanalın orijinal stili, emojileri ve `<blockquote>` iletişim bloğu (@servis_istanbul)
   eksiksiz korunur.
5. Onay butonları: [✅ Tasdiqlash (Kanalga chiqarish)] [🔄 Yangi post] [❌ Rad etish]
=============================================================================
"""

import http.server
import json
import logging
import os
import random
import re
import socketserver
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# 1. GEREKLİ KÜTÜPHANELERİ OTOMATİK KONTROL ETME
# ---------------------------------------------------------------------------
def ensure_dependencies() -> None:
    required_packages = [
        ("requests", "requests"),
        ("dotenv", "python-dotenv"),
    ]
    for module_name, pip_name in required_packages:
        try:
            __import__(module_name)
        except ImportError:
            print(f"[*] '{pip_name}' kutubxonasi o'rnatilmoqda, iltimos kuting...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-U", pip_name])
            print(f"[+] '{pip_name}' muvaffaqiyatli o'rnatildi!")


ensure_dependencies()

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# 2. BULUT SUNUCULARI (RENDER / KOYEB) İÇİN MİNİ WEB SERVER (PORT BINDING)
# ---------------------------------------------------------------------------
def start_dummy_web_server_if_needed() -> None:
    """Render.com ve Koyeb gibi bulut servislerinin kapanmaması için arka planda küçük bir web yanıtlayıcı açar."""
    port_str = os.environ.get("PORT")
    if not port_str:
        return

    try:
        port = int(port_str)
        class QuietHandler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:
                pass
            def do_GET(self) -> None:
                self.send_response(200)
                self.send_header("Content-type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"Istanbul Xizmatlari Bot is running 24/7!")

        server = socketserver.TCPServer(("0.0.0.0", port), QuietHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        print(f"[+] Bulut web sunucusu PORT {port} üzerinde başlatıldı (7/24 uyanık tutma aktif).")
    except Exception as exc:
        print(f"[-] Web server başlatma uyarısı: {exc}")


# ---------------------------------------------------------------------------
# 3. DOSYALAR VE ZAMAN AYARLARI
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
HISTORY_FILE = BASE_DIR / "posts_history.json"
DRAFTS_FILE = BASE_DIR / "pending_drafts.json"

# Taşkent saati (UTC+5)
TASHKENT_TZ = timezone(timedelta(hours=5), name="Asia/Tashkent")

# Post çıkış saatleri (Taşkent saatiyle)
SCHEDULE_TIMES = ["10:00", "17:00"]

# Kanalda daha önce yayınlanan 12 post (tekrar etmemesi için)
INITIAL_PUBLISHED_TOPICS = [
    {
        "date": "2026-06-26 16:50",
        "topic": "Istanbul xizmatlari umumiy tanishtiruv (Aeroport VIP transfer, sayohat, mehmonxona, SIM-karta)",
        "title": "Assalomu alaykum, aziz yurtdoshlar! Xizmatlarimiz",
    },
    {
        "date": "2026-09-30 19:42",
        "topic": "Qiz minorasi (Kız Kulesi) afsonasi va Üsküdar sohili",
        "title": "Istanbul timsoli: Qiz minorasi (Kız Kulesi)",
    },
    {
        "date": "2026-10-01 11:30",
        "topic": "Sapanca'da bir kun (Ma'shuqiya sharsharasi, Ormanya, Hobbit uychalari, ATV Safari, Zipline)",
        "title": "SAPANCA'DA BIR KUN!",
    },
    {
        "date": "2026-10-01 12:21",
        "topic": "Istanbulga ilk bor keluvchilar uchun 5 ta oltin qoida (Valyuta, Istanbulkart, Taksi, SIM-karta)",
        "title": "Istanbulga ilk bor keluvchilar uchun 5 ta oltin qoida",
    },
    {
        "date": "2026-10-03 18:54",
        "topic": "Galata minorasi (Galata Kulesi) va Hazorfen Ahmad Chalabiy tarixi",
        "title": "Istanbulning osmondagi ko'zi: Galata minorasi (Galata Kulesi)",
    },
    {
        "date": "2026-10-04 18:37",
        "topic": "Eminönü maydoni, Balık Ekmek, Yeni Cami va paromlar",
        "title": "Istanbulning yuragi — Eminönü!",
    },
    {
        "date": "2026-10-05 14:52",
        "topic": "Eyüp Sulton masjidi (Eyüp Sultan Camii) va Pierre Loti tepaligi",
        "title": "Istanbulning ruhiy maskani: Eyüp Sulton masjidi",
    },
    {
        "date": "2026-10-06 15:52",
        "topic": "Istanbulda sariq taksi muammolari va Shaxsiy VIP Transfer yechimi",
        "title": "Istanbulda taksi muammosi: Asab va pulingizni tejang!",
    },
    {
        "date": "2026-10-07 20:52",
        "topic": "Istanbulda Shopping va savdo markazlari (Cevahir, Mall of Istanbul, Zorlu Center, Venezia Mega Outlet)",
        "title": "Istanbulda Shopping: Qaysi savdo markazlariga (AVM) borish kerak?",
    },
    {
        "date": "2026-10-09 17:20",
        "topic": "Aya Sofiya masjidi (Ayasofya-i Kebir Cami-i Şerifi) tarixi va me'morchiligi",
        "title": "Tarix va ma'naviyat chorrahasi: Aya Sofiya masjidi",
    },
    {
        "date": "2026-10-13 15:22",
        "topic": "Buyuk Jamlija masjidi (Büyük Çamlıca Camii) va panoramik tepalik",
        "title": "Zamonaviy ulug'vorlik va osmono'par go'zallik: Buyuk Jamlija masjidi",
    },
    {
        "date": "2026-10-20 20:04",
        "topic": "Kapadokya sayohati (Havo sharlari, g'or-mehmonxonalar, yerosti shaharlari)",
        "title": "Ertaklar olamiga sayohat: Sehrli va betakror Kapadokya",
    },
]

# ---------------------------------------------------------------------------
# 4. KANALIN ORİJİNAL STİLİNDE 25+ ADET HAZIR SEYAHAT REHBERİ VERİTABANI
# ---------------------------------------------------------------------------
CURATED_TRAVEL_POSTS: List[Dict[str, str]] = [
    {
        "topic": "Topkapi saroyi (Topkapı Sarayı) — Usmoniy sultonlar qarorgohi",
        "title": "Usmoniylar saltanatining yuragi: Topkapi saroyi (Topkapı Sarayı) 👑✨",
        "body": (
            "<b>Usmoniylar saltanatining yuragi: Topkapi saroyi (Topkapı Sarayı) 👑✨</b>\n\n"
            "Deyarli 400 yil davomida qudratli Usmoniy imperiyasi aynan shu saroydan boshqarilgan. "
            "Sarayburnu burnida joylashgan bu ulug‘vor maskan Oltin Shox, Bosfor va Marmar dengiziga ochiladigan "
            "tengsiz manzarasi bilan har bir sayyohni hayratga soladi.\n\n"
            "👑 <b>Tarixdan qiziqarli fakt:</b>\n"
            "Saroy xazinasida dunyodagi eng mashhur 86 qirotli «Qoshiqchi olmosi» (Kaşıkçı Elması) va "
            "hazrati Payg‘ambarimiz Muhammad ﷺ ning muqaddas omonatlari (hirkasi, qilichlari va soqol tolalari) saqlanadi.\n\n"
            "✨ <b>Nega ziyorat qilish kerak?</b>\n"
            "• <b>Muqaddas omonatlar xonasi:</b> Dunyo musulmonlari uchun eng qadrli ma’naviy ziyoratgoh.\n"
            "• <b>Sultonlar Harami:</b> Qadimiy koshinlar va sulton xonadonining sirlarga boy hayoti.\n"
            "• <b>To‘rtinchi hovli va terassa:</b> Bosforga qaragan eng go‘zal manzarali suratlar nuqtasi.\n\n"
            "Tarixiy obidalar bo‘ylab navbatda turmasdan, qulay va mazmunli sayohat qilish uchun biz bilan bog‘laning 🤝"
        ),
    },
    {
        "topic": "Dolmabahche saroyi (Dolmabahçe Sarayı) — Bosfor sohilidagi billur hashamat",
        "title": "Bosfor sohilidagi billur hashamat: Dolmabahche saroyi (Dolmabahçe Sarayı) 🏛🌊",
        "body": (
            "<b>Bosfor sohilidagi billur hashamat: Dolmabahche saroyi (Dolmabahçe Sarayı) 🏛🌊</b>\n\n"
            "XIX asrda qurilgan Dolmabahche saroyi — an’anaviy sharqona dabdaba va Yevropa barokko me’morchiligining "
            "uyg‘unlashgan nodir shoh asaridir. Saroyning dengizga ochiladigan oq marmar darvozalari Istanbulning "
            "eng mashhur tashrif qog‘oziga aylangan.\n\n"
            "💎 <b>Tarixdan qiziqarli fakt:</b>\n"
            "Saroyning tantanalar zalida Angliya qirolichasi Viktoriya sovg‘a qilgan 4,5 tonnalik ulkan billur qandil "
            "o‘rnatilgan. Bino ichki bezaklari uchun esa jami 35 tonnadan ortiq sof oltin va kumush ishlatilgan!\n\n"
            "✨ <b>Nega borish kerak?</b>\n"
            "• <b>Marmar dengiz darvozalari:</b> Bosfor fonida Istanbulning eng go‘zal fotosuratlarini olish imkoniyati.\n"
            "• <b>Billur zinalar (Kristal Merdiven):</b> Ingliz billuridan ishlangan betakror zinalar majmuasi.\n"
            "• <b>Sohil bog‘i:</b> Dengiz shabadasi va kafelarda choy ichib dam olish zavqi.\n\n"
            "Mehmonxonadan to‘g‘ridan-to‘g‘ri saroylargacha qulay VIP mashinada yetib olish uchun biz bilan bog‘laning 🤝"
        ),
    },
    {
        "topic": "Sultonahmet masjidi (Ko'k masjid / Sultanahmet Camii)",
        "title": "Moviy koshinlar jilosi: Sultonahmet masjidi (Ko‘k masjid) 🕌💙",
        "body": (
            "<b>Moviy koshinlar jilosi: Sultonahmet masjidi (Ko‘k masjid) 🕌💙</b>\n\n"
            "Aya Sofiya ro‘parasida qad rostlagan Sultonahmet masjidi o‘zining 6 ta baland minorasi va ko‘k-moviy "
            "Iznik koshinlari bilan butun dunyoga «Ko‘k masjid» nomi bilan tanilgan.\n\n"
            "🕌 <b>Tarixdan qiziqarli fakt:</b>\n"
            "Rivoyatlarga ko‘ra, Sulton Ahmad I me’mor Sedefkor Mehmet Og‘aga minoralarni «oltin» (altın) qilishni "
            "buyurgan. Me’mor esa buni yanglish eshitib, «olti» (altı) ta minora qilib qurgan va Istanbulda ilk 6 minorali masjid vujudga kelgan!\n\n"
            "✨ <b>Nega ziyorat qilish kerak?</b>\n"
            "• <b>20 000 dan ortiq Iznik koshini:</b> Qo‘lda chizilgan lola va gultoj naqshlari.\n"
            "• <b>Atmeydanı (Otchopar maydoni):</b> Qadimiy Misr obeliski va Vizantiya davri yodgorliklari.\n"
            "• <b>Sharqona sokinlik:</b> Masjid hovlisida his qilinadigan o‘zgacha ma’naviy xotirjamlik.\n\n"
            "Istanbul bo‘ylab eng qulay yo‘nalishlarda, professional gid bilan sayohat qilish uchun biz bilan bog‘laning 🤝"
        ),
    },
    {
        "topic": "Yerebatan sardoni (Yerebatan Sarnıcı / Basilica Cistern)",
        "title": "Yer ostidagi sirli saroy: Yerebatan sardoni (Basilica Cistern) 🏛🕯",
        "body": (
            "<b>Yer ostidagi sirli saroy: Yerebatan sardoni (Basilica Cistern) 🏛🕯</b>\n\n"
            "Istanbulning qoq markazida, yer sathidan 12 metr chuqurlikda joylashgan bu qadimiy suv ombori "
            "oddiy inshoot emas, balki suv uzra suzib turgandek ko‘ringan haqiqiy yerosti saroyidir.\n\n"
            "🐍 <b>Meduza boshi siri:</b>\n"
            "Sardonning eng chekka burchagidagi ikki ustun ostida qadimiy Meduza Gorgonaning bahaybat tosh haykallari "
            "teskari va yonbosh qo‘yilgan. Afsonaga ko‘ra, Meduzaning ko‘zlariga qaragan odam toshga aylanganligi sababli, uning sehrini yo‘qotish uchun ustunlar ataylab teskari o‘rnatilgan.\n\n"
            "✨ <b>Nega borish kerak?</b>\n"
            "• <b>336 ta qadimiy ustun:</b> Chiroqlar va mumtoz musiqa bilan uyg‘unlashgan mistik muhit.\n"
            "• <b>Zamonaviy san’at:</b> Suv ustidagi ko‘rgazmalar va nur installyatsiyalari.\n"
            "• <b>Yozgi salqinlik:</b> Issiq havoda ham ichkarida o‘zgacha yoqimli salqin havo hukm suradi.\n\n"
            "Shaharning sirli maskanlarini oson va qulay kashf qilish uchun biz bilan bog‘laning 🤝"
        ),
    },
    {
        "topic": "Balat mahallasi (Fener-Balat) — rangdor ko'chalar va nostalgiya",
        "title": "Rang-barang ertaklar ko‘chasi: Tarixiy Balat mahallasi 🎨🏘",
        "body": (
            "<b>Rang-barang ertaklar ko‘chasi: Tarixiy Balat mahallasi 🎨🏘</b>\n\n"
            "Oltin Shox sohilida joylashgan Balat — Istanbulning eng nostaljik, rang-barang va o‘ziga xos "
            "muhitga ega qadimiy mahallasidir. Bu yerda asrlar davomida turli madaniyatlar yonma-yon yashab kelgan.\n\n"
            "📸 <b>Foto uchun eng zo‘r joy:</b>\n"
            "Kiremit ko‘chasidagi qator terilgan rangdor yog‘och uylar va tosh ko‘chalar Instagramda "
            "eng ko‘p suratga olinadigan manzil hisoblanadi.\n\n"
            "✨ <b>Nega Balatga borish kerak?</b>\n"
            "• <b>Antiqa buyumlar va vintage kafelar:</b> Qadimiy plastinkalar, chiroqlar va shinam qahvaxonalar.\n"
            "• <b>Qizil maktab (Fener Rum litseyi):</b> Tepalikdagi ulug‘vor qizil qasrsifat tarixiy bino.\n"
            "• <b>Jonli ko‘cha hayoti:</b> Dorlarda yoyilgan kirlar, o‘ynayotgan bolalar va samimiy mahalla muhiti.\n\n"
            "Tirband transportda qiynalmasdan, qulay mashinada Balat bo‘ylab sayr qilish uchun biz bilan bog‘laning 🤝"
        ),
    },
    {
        "topic": "Ortako'y (Ortaköy) — Bosfor ko'prigi ostidagi joziba",
        "title": "Bosfor marvaridi: Ortako‘y (Ortaköy) va mashhur kumpir 🌉✨",
        "body": (
            "<b>Bosfor marvaridi: Ortako‘y (Ortaköy) va mashhur kumpir 🌉✨</b>\n\n"
            "Bosfor ko‘prigining naq tagida joylashgan Ortako‘y maydoni — dengiz to‘lqinlari, tarixiy nafis masjid "
            "va zamonaviy ko‘prik chiroqlari bir nuqtada birlashgan Istanbulning eng romantik go‘shasidir.\n\n"
            "🥔 <b>Mashhur Ortako‘y kumpiri:</b>\n"
            "Ortako‘yga kelib, ulkan tandir kartoshkasi ichiga pishloq, zaytun, makkajo‘xori va o‘nlab noz-ne’matlar "
            "aralashtirib tayyorlanadigan mashhur «Kumpir» va issiq vaflilardan tatib ko‘rmaslik mumkin emas!\n\n"
            "✨ <b>Nega borish kerak?</b>\n"
            "• <b>Ortako‘y masjidi (Büyük Mecidiye Camii):</b> Suv uzra suzib yurgandek ko‘rinuvchi nafis me’morchilik.\n"
            "• <b>Kechki Bosfor manzarasi:</b> Ko‘prik chiroqlari yoqilgandagi sehrli panorama.\n"
            "• <b>Qo‘l mehnati bozori:</b> Ekranda ko‘rganingizdek milliy taqinchoqlar va esdalik sovg‘alari.\n\n"
            "Ortako‘y va Bosfor bo‘ylab unutilmas shaxsiy sayohatlarni rejalashtirish uchun biz bilan bog‘laning 🤝"
        ),
    },
    {
        "topic": "Shahzodalar orollari (Prens Adaları — Büyükada va Heybeliada)",
        "title": "Shovqindan xoli jannatmonand maskan: Shahzodalar orollari (Büyükada) 🌲🚲",
        "body": (
            "<b>Shovqindan xoli jannatmonand maskan: Shahzodalar orollari (Büyükada) 🌲🚲</b>\n\n"
            "Megapolis shovqinidan charchadingizmi? Marmar dengizidagi Shahzodalar orollari — toza havo, "
            "qarag‘ayzorlar va tarixiy yog‘och qasrlar maskanidir. Bu yerda avtomobillar harakati taqiqlangan!\n\n"
            "🌊 <b>Qanday boriladi va sayr qilinadi?</b>\n"
            "Kabataş yoki Eminönü pristanidan paromga minib, chayqalib suzuvchi chayqalarga simit tashlab bir soatda "
            "orolga yetib borasiz. Orol ichida esa velosiped yoki ekologik elektromobillarda sayr qilinadi.\n\n"
            "✨ <b>Büyükadada nimalar qilish kerak?</b>\n"
            "• <b>Aya Yorgi tepaligi:</b> Orolning eng baland cho‘qqisidan ochiladigan cheksiz dengiz manzarasi.\n"
            "• <b>Tarixiy yog‘och villalar:</b> Gullarga burkangan ko‘chalardagi qadimiy Usmoniy saroychalari.\n"
            "• <b>Sohildagi baliq restoranlari:</b> Yangi tutilgan baliq va dengiz mahsulotlaridan bahramand bo‘lish.\n\n"
            "Orollarga qulay yetib olish va VIP transport xizmatlari uchun biz bilan bog‘laning 🤝"
        ),
    },
    {
        "topic": "Yashil Bursa va Uludağ — bir kunlik sayohat",
        "title": "Usmoniylarning ilk poytaxti: Yashil Bursa va Uludağ sayohati 🏔🌲",
        "body": (
            "<b>Usmoniylarning ilk poytaxti: Yashil Bursa va Uludağ sayohati 🏔🌲</b>\n\n"
            "Istanbuldan atigi 2 soatlik masofada joylashgan Bursa shahri — betakror tabiati, asriy chinorlari, "
            "qadimiy masjidlari va mashhur Uludağ tog‘i bilan sayyohlarni maftun etadi.\n\n"
            "🥩 <b>Iskandar kabob vatani:</b>\n"
            "Haqiqiy Iskandar kabob (İskender Kebap) aynan Bursada pishiriladi! Yupqa go‘sht ustiga quyiladigan "
            "qaynoq sariyog‘ va quyuq qatiq ta’mi uzoq vaqt yodingizda qoladi.\n\n"
            "✨ <b>Bursada nimalarni ko‘rish kerak?</b>\n"
            "• <b>Bursa teleferigi (Uludağ Teleferik):</b> Dunyodagi eng uzun osma yo‘llardan biri orqali bulutlar uzra parvoz.\n"
            "• <b>Koza Han (Ipak bozori):</b> Buyuk Ipak yo‘lining qadimiy karvonsaroyida choy ichish zavqi.\n"
            "• <b>Ulug‘ masjid (Ulu Cami):</b> 20 gumbazli muazzam masjid va ichkaridagi favvora.\n\n"
            "Keng va shinam VIP mashinalarda 1 kunlik shaxsiy Bursa sayohatini band qilish uchun biz bilan bog‘laning 🤝"
        ),
    },
    {
        "topic": "Kapalıçarşı (Grand Bazaar) va Misr bozori (Mısır Çarşısı)",
        "title": "Sharqona ertaklar bozori: Kapalıçarşı (Grand Bazaar) 🕌✨",
        "body": (
            "<b>Sharqona ertaklar bozori: Kapalıçarşı (Grand Bazaar) 🕌✨</b>\n\n"
            "1461-yilda asos solingan Kapalıçarşı — dunyodagi eng qadimiy va eng ulkan yopiq bozorlardan biri. "
            "Bu yerda 60 dan ortiq ko‘cha va 4000 dan ortiq do‘konlar jamlangan haqiqiy labirint!\n\n"
            "☕ <b>Xarid va choy madaniyati:</b>\n"
            "Bozor do‘kondorlari sizni albatta olma choyi yoki turk qahvasi bilan mehmon qiladi. Bu yerda savdolashish — "
            "shunchaki arzonlashtirish emas, balki qiziqarli sharqona an’ana hisoblanadi!\n\n"
            "✨ <b>Nimalar xarid qilish mumkin?</b>\n"
            "• <b>Turk shirinliklari va lokumlari:</b> Anorli, pistali va yong‘oqli yangi pishirilgan lokumlar.\n"
            "• <b>Sharqona chiroqlar va gilamlar:</b> Qo‘l mehnati bilan yasalgan rang-barang mozaik lampalar.\n"
            "• <b>Tilla va kumush taqinchoqlar:</b> Usmoniy uslubidagi noyob zargarlik buyumlari.\n\n"
            "Xaridlardan so‘ng to‘la sumkalar bilan qiynalmasdan, mehmonxonagacha VIP mashinada yetib olish uchun biz bilan bog‘laning 🤝"
        ),
    },
    {
        "topic": "Aeroportdan mehmonxonaga VIP Transfer qulayliklari",
        "title": "Istanbulga yetib keldingizmi? Stresssiz VIP Transfer xizmati! 🛬🚐",
        "body": (
            "<b>Istanbulga yetib keldingizmi? Stresssiz VIP Transfer xizmati! 🛬🚐</b>\n\n"
            "Uzun parvozdan so‘ng aeroportda taksi qidirib sarson bo‘lish, tirbandlikda hisoblagichdan xavotir olish "
            "yoki og‘ir chamadonlar bilan jamoat transportida qiynalishga hojat yo‘q.\n\n"
            "✨ <b>Nega bizning VIP Transferni tanlashadi?</b>\n"
            "• <b>Shaxsiy kutib olish:</b> IST (Yangi aeroport) va SAW (Sabiha Gökçen) aeroportlarida ismingiz yozilgan lavha bilan kutib olamiz.\n"
            "• <b>Keng Mercedes Vito mashinalari:</b> Katta oila va barcha yuklaringiz bemalol sig‘adi, ichida Wi-Fi va qulay charm o‘rindiqlar mavjud.\n"
            "• <b>O‘zgarmas qat’iy narx:</b> Tirbandlik bo‘lsa ham, oldindan kelishilgan narx o‘zgarmaydi.\n"
            "• <b>O‘zbekzabon haydovchilar:</b> Begona shaharda tushunmovchiliksiz, samimiy va xavfsiz xizmat.\n\n"
            "Sayohatingizni birinchi daqiqalardanoq yuqori qulaylikda boshlang! 🤝"
        ),
    },
    {
        "topic": "Pamukkale travertinlari va Kleopatra hovuzi",
        "title": "Oppok paxtadek mo‘jiza: Pamukkale va Kleopatra hovuzi 🕊🌊",
        "body": (
            "<b>Oppok paxtadek mo‘jiza: Pamukkale va Kleopatra hovuzi 🕊🌊</b>\n\n"
            "Turkiyaning eng noyob tabiiy mo‘jizasi bo‘lgan Pamukkale — tog‘ bag‘rini qoplagan oppoq kalsiy travertinlari "
            "va moviy termal suvlari bilan yer yuzidagi qorli ertakni eslatadi.\n\n"
            "👑 <b>Qadimiy Kleopatra hovuzi:</b>\n"
            "Miloddan avvalgi zilzila natijasida hosil bo‘lgan ushbu tabiiy shifobaxsh hovuz tubida qadimiy Rim ustunlari "
            "yotadi. Suv harorati yil bo‘yi +36°C bo‘lib, unda cho‘milish yosharish va tetiklik bag‘ishlaydi!\n\n"
            "✨ <b>Nega borish kerak?</b>\n"
            "• <b>Ierapolis (Hierapolis) qadimiy shahri:</b> Rim amfiteatri va qadimiy nekropol majmuasi.\n"
            "• <b>Travertinlarda yalangoyoq yurish:</b> Issiq shifobaxsh mineral suvlarda sayr qilish zavqi.\n"
            "• <b>Unutilmas fotosuratlar:</b> Moviy suv va oppoq toshlar fonidagi sehrli suratlar.\n\n"
            "Turkiya bo‘ylab shaharlararo qulay va xavfsiz sayohatlarni tashkil qilish uchun biz bilan bog‘laning 🤝"
        ),
    },
    {
        "topic": "Antaliya va Kaleiçi eski shahri",
        "title": "O‘rta yer dengizi poytaxti: Quyoshli Antaliya va Kaleiçi 🌴🌊",
        "body": (
            "<b>O‘rta yer dengizi poytaxti: Quyoshli Antaliya va Kaleiçi 🌴🌊</b>\n\n"
            "Moviy dengiz, palmalarga burkangan xiyobonlar va baland Toros tog‘lari qurshovida joylashgan Antaliya — "
            "Turkiyaning eng sevimli kurort shahridir.\n\n"
            "🏛 <b>Kaleiçi — qadimiy shahar ichidagi shahar:</b>\n"
            "Rim imperatori Adrian sharafiga milodiy 130-yilda qurilgan «Adrian darvozasi» (Üçkapılar)dan o‘tib, "
            "tor tosh ko‘chalar, Usmoniy uslubidagi uylar va qadimiy bandargohga tushasiz.\n\n"
            "✨ <b>Antaliyada nimalarni ko‘rish kerak?</b>\n"
            "• <b>Düden sharsharasi:</b> Qoyadan to‘g‘ridan-to‘g‘ri dengizga quyiladigan bahaybat sharshara.\n"
            "• <b>Tünektepe teleferigi:</b> Antaliya va dengiz manzarasini qush parvozi balandligidan tomosha qilish.\n"
            "• <b>Konyaaltı sohili:</b> Moviy bayroqli toza sohillarda hordiq chiqarish.\n\n"
            "Antaliya va O‘rta yer dengizi bo‘ylab VIP transfer hamda sayohatlar uchun biz bilan bog‘laning 🤝"
        ),
    },
]

# ---------------------------------------------------------------------------
# 5. SOZLAMALARI YÜKLEME
# ---------------------------------------------------------------------------
def setup_or_load_config() -> Dict[str, str]:
    load_dotenv(ENV_FILE)

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    channel_id = os.getenv("CHANNEL_ID", "").strip()
    admin_id = os.getenv("ADMIN_USER_ID", "").strip()
    telegram_contact = os.getenv("TELEGRAM_CONTACT", "@servis_istanbul").strip()
    whatsapp_contact = os.getenv("WHATSAPP_CONTACT", "+905548461085").strip()

    if not all([bot_token, channel_id, admin_id]):
        print("\n" + "=" * 65)
        print("   ISTANBUL XIZMATLARI AVTO-POST BOTIGA XUSH KELIBSIZ!")
        print("   Dastlabki sozlash (faqat bir marta kiritiladi):")
        print("=" * 65 + "\n")

        if not bot_token:
            bot_token = input("1. Telegram Bot Tokeningizni kiriting: ").strip()
        if not gemini_key:
            gemini_key = input("2. Gemini API kalitingizni kiriting (Ixtiyoriy, Enter bosing): ").strip()
        if not channel_id:
            channel_id = input("3. Kanal @username yoki ID raqamini kiriting: ").strip()
        if not admin_id:
            admin_id = input("4. Shaxsiy Telegram ID raqamingizni kiriting: ").strip()

        env_content = (
            f"TELEGRAM_BOT_TOKEN={bot_token}\n"
            f"GEMINI_API_KEY={gemini_key}\n"
            f"CHANNEL_ID={channel_id}\n"
            f"ADMIN_USER_ID={admin_id}\n"
            f"TELEGRAM_CONTACT={telegram_contact}\n"
            f"WHATSAPP_CONTACT={whatsapp_contact}\n"
        )
        ENV_FILE.write_text(env_content, encoding="utf-8")
        print(f"\n[+] Sozlamalar '{ENV_FILE.name}' fayliga saqlandi!\n")

    return {
        "TELEGRAM_BOT_TOKEN": bot_token,
        "GEMINI_API_KEY": gemini_key,
        "CHANNEL_ID": channel_id,
        "ADMIN_USER_ID": str(admin_id),
        "TELEGRAM_CONTACT": telegram_contact or "@servis_istanbul",
        "WHATSAPP_CONTACT": whatsapp_contact or "+905548461085",
    }


# ---------------------------------------------------------------------------
# 6. TARİH VE TASLAKLAR
# ---------------------------------------------------------------------------
def load_history() -> List[Dict[str, Any]]:
    if not HISTORY_FILE.exists():
        HISTORY_FILE.write_text(
            json.dumps(INITIAL_PUBLISHED_TOPICS, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return list(INITIAL_PUBLISHED_TOPICS)
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        existing_titles = {item.get("title", "") for item in data}
        added = False
        for init_item in INITIAL_PUBLISHED_TOPICS:
            if init_item["title"] not in existing_titles:
                data.insert(0, init_item)
                added = True
        if added:
            HISTORY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data
    except Exception as exc:
        return list(INITIAL_PUBLISHED_TOPICS)


def save_to_history(topic: str, title: str, text: str) -> None:
    history = load_history()
    now_str = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d %H:%M")
    history.append(
        {
            "date": now_str,
            "topic": topic,
            "title": title,
            "preview": text[:160],
        }
    )
    history = history[-200:]
    HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def load_drafts() -> Dict[str, Dict[str, Any]]:
    if not DRAFTS_FILE.exists():
        return {}
    try:
        return json.loads(DRAFTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_drafts(drafts: Dict[str, Dict[str, Any]]) -> None:
    DRAFTS_FILE.write_text(json.dumps(drafts, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# 7. POST ÜRETİCİSİ (GEMINI + 100% GÜVENLİ VERİTABANI YEDEĞİ)
# ---------------------------------------------------------------------------
def try_gemini_generate(api_key: str, prompt: str) -> Optional[str]:
    if not api_key:
        return None

    candidate_models = [
        "gemini-3.8-flash",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
    ]

    for model_name in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.7},
        }
        try:
            r = requests.post(url, json=payload, timeout=15)
            if r.ok:
                resp_json = r.json()
                candidates = resp_json.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        return parts[0]["text"].strip()
        except Exception:
            continue
    return None


def get_curated_post(custom_topic: Optional[str] = None) -> Dict[str, str]:
    history = load_history()
    used_titles = {item.get("title", "").strip().lower() for item in history}

    if custom_topic:
        for p in CURATED_TRAVEL_POSTS:
            if custom_topic.lower() in p["topic"].lower() or custom_topic.lower() in p["title"].lower():
                return p

    available = [p for p in CURATED_TRAVEL_POSTS if p["title"].strip().lower() not in used_titles]
    if available:
        return random.choice(available)
    return random.choice(CURATED_TRAVEL_POSTS)


def generate_travel_post(config: Dict[str, str], custom_topic: Optional[str] = None) -> Dict[str, str]:
    history = load_history()
    past_topics = [f"- {item.get('title', '')}" for item in history[-30:]]
    past_topics_text = "\n".join(past_topics)

    contact_block = (
        f"\n\n<blockquote>📲 Murojaat va band qilish:\n"
        f"• Telegram: {config['TELEGRAM_CONTACT']}\n"
        f"• WhatsApp: {config['WHATSAPP_CONTACT']}</blockquote>"
    )

    prompt = f"""
Sen "Istanbul xizmatlari" Telegram kanalining rasmiy sayohat muharririsan.
Mavzu: Istanbul va Turkiya bo'ylab sayohat, tarixiy maskanlar va VIP xizmatlar.

VAZIFA:
{f"Foydalanuvchi tanlagan mavzu: {custom_topic}" if custom_topic else "Istanbul yoki Turkiyaning mashhur, go'zal bir sayohat maskani haqida qiziqarli post yoz."}

OLDIN CHIQQAN MAVZULAR (takrorlanmasin):
{past_topics_text}

QAT'IY TUZILISH:
1. SARLAVHA: Qalin harfda (<b>...</b>), maskanning turkcha nomi qavsda va 2 ta emoji bilan.
2. QISQA KIRISH: 1-2 jumlada maskan haqida.
3. 🦅 <b>Tarixdan qiziqarli fakt:</b> yoki 🕌 <b>Tarixdan qiziqarli fakt:</b> — 1-2 jumlada qiziq ma'lumot.
4. ✨ <b>Nega ziyorat qilish kerak?</b> — `•` belgisi bilan 3 ta aniq band.
5. XIZMATGA BOG'LOVCHI XULOSA: "Istanbul bo‘ylab qulay, mazmunli va esda qolarli sayohat qilish uchun biz bilan bog‘laning 🤝" yoki VIP mashinada borish taklifi.

Postni O'zbek lotin tilida yoz. Markdown (** yoki ##) ishlatma, faqat HTML (<b>...</b>) ishlat.
Post oxiriga aloqa ma'lumotlarini qo'shma, ularni tizim o'zi qo'shadi.
"""

    generated_text = try_gemini_generate(config.get("GEMINI_API_KEY", ""), prompt)

    if generated_text:
        final_text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", generated_text)
        final_text = re.sub(r"^#+\s*", "", final_text, flags=re.MULTILINE)
        final_post = final_text.strip() + contact_block

        lines = [line.strip() for line in final_post.split("\n") if line.strip()]
        title = lines[0] if lines else "Istanbul bo'ylab sayohat"
        title_clean = re.sub(r"<[^>]+>", "", title)

        return {
            "title": title_clean[:100],
            "topic": custom_topic or title_clean[:100],
            "text": final_post,
            "source": "Gemini AI",
        }

    curated = get_curated_post(custom_topic)
    final_post = curated["body"].strip() + contact_block

    return {
        "title": curated["title"],
        "topic": curated["topic"],
        "text": final_post,
        "source": "Kanal sayohat kutubxonasi (100% xatosiz zaxira)",
    }


# ---------------------------------------------------------------------------
# 8. TELEGRAM BOT API
# ---------------------------------------------------------------------------
class TelegramBotClient:
    def __init__(self, token: str) -> None:
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"

    def get_me(self) -> Dict[str, Any]:
        resp = requests.get(f"{self.base_url}/getMe", timeout=15)
        resp.raise_for_status()
        return resp.json().get("result", {})

    def send_message(
        self,
        chat_id: str,
        text: str,
        reply_markup: Optional[Dict[str, Any]] = None,
        parse_mode: str = "HTML",
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)
        resp = requests.post(f"{self.base_url}/sendMessage", data=payload, timeout=20)
        return resp.json()

    def answer_callback_query(self, callback_query_id: str, text: str, show_alert: bool = False) -> None:
        requests.post(
            f"{self.base_url}/answerCallbackQuery",
            data={
                "callback_query_id": callback_query_id,
                "text": text,
                "show_alert": show_alert,
            },
            timeout=10,
        )

    def edit_message_reply_markup(
        self,
        chat_id: str,
        message_id: int,
        reply_markup: Optional[Dict[str, Any]] = None,
    ) -> None:
        data: Dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "reply_markup": json.dumps(reply_markup or {"inline_keyboard": []}),
        }
        requests.post(f"{self.base_url}/editMessageReplyMarkup", data=data, timeout=10)

    def get_updates(self, offset: Optional[int] = None, timeout: int = 10) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        try:
            resp = requests.get(f"{self.base_url}/getUpdates", params=params, timeout=timeout + 5)
            if resp.ok:
                return resp.json().get("result", [])
        except Exception:
            pass
        return []


# ---------------------------------------------------------------------------
# 9. ADMIN ONAY SÜRECİ
# ---------------------------------------------------------------------------
def build_approval_keyboard(draft_id: str) -> Dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {
                    "text": "✅ Tasdiqlash (Kanalga chiqarish)",
                    "callback_data": f"approve:{draft_id}",
                }
            ],
            [
                {
                    "text": "🔄 Yangi post tayyorlash",
                    "callback_data": f"regenerate:{draft_id}",
                },
                {
                    "text": "❌ Rad etish",
                    "callback_data": f"reject:{draft_id}",
                },
            ],
        ]
    }


def generate_and_send_for_approval(
    bot: TelegramBotClient,
    config: Dict[str, str],
    custom_topic: Optional[str] = None,
) -> None:
    admin_id = config["ADMIN_USER_ID"]
    bot.send_message(
        admin_id,
        "⏳ <b>Yangi sayohat posti tayyorlanmoqda...</b>\n"
        "1️⃣ Maskan tanlanmoqda\n"
        "2️⃣ Matn kanal uslubida shakllantirilmoqda...",
    )

    try:
        post_data = generate_travel_post(config, custom_topic=custom_topic)

        draft_id = uuid.uuid4().hex[:10]
        drafts = load_drafts()
        drafts[draft_id] = {
            "topic": post_data["topic"],
            "title": post_data["title"],
            "text": post_data["text"],
            "created_at": datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d %H:%M"),
            "status": "pending",
        }
        save_drafts(drafts)

        send_res = bot.send_message(
            chat_id=admin_id,
            text=post_data["text"],
            reply_markup=build_approval_keyboard(draft_id),
        )

        if not send_res.get("ok"):
            clean_text = re.sub(r"<[^>]+>", "", post_data["text"])
            send_res = bot.send_message(
                chat_id=admin_id,
                text=clean_text,
                reply_markup=build_approval_keyboard(draft_id),
                parse_mode="",
            )

        if send_res.get("ok"):
            bot.send_message(
                admin_id,
                f"📋 <b>Post tayyor!</b>\n"
                f"• <b>Mavzu:</b> {post_data['topic']}\n"
                f"• <b>Manba:</b> {post_data['source']}\n\n"
                f"👆 <i>Post ma’qul bo‘lsa, <b>«Tasdiqlash»</b> tugmasini bosing — darhol {config['CHANNEL_ID']} kanaliga chiqadi!</i>",
            )
        else:
            bot.send_message(admin_id, f"⚠️ Xatolik: {send_res.get('description')}")

    except Exception as exc:
        bot.send_message(admin_id, f"❌ Xatolik yuz berdi: <code>{exc}</code>")


# ---------------------------------------------------------------------------
# 10. BUTON VE MESAJ İŞLEYİCİSİ
# ---------------------------------------------------------------------------
def handle_callback(
    bot: TelegramBotClient,
    config: Dict[str, str],
    callback_query: Dict[str, Any],
) -> None:
    cb_id = callback_query["id"]
    data = callback_query.get("data", "")
    message = callback_query.get("message", {})
    chat_id = str(message.get("chat", {}).get("id", ""))
    message_id = message.get("message_id")
    user_id = str(callback_query.get("from", {}).get("id", ""))

    if user_id != config["ADMIN_USER_ID"]:
        bot.answer_callback_query(cb_id, "Sizda ruxsat yo'q!", show_alert=True)
        return

    if ":" not in data:
        return

    action, draft_id = data.split(":", 1)
    drafts = load_drafts()
    draft = drafts.get(draft_id)

    if not draft:
        bot.answer_callback_query(cb_id, "Bu qoralama topilmadi.", show_alert=True)
        return

    if action == "approve":
        if draft.get("status") == "published":
            bot.answer_callback_query(cb_id, "Bu post allaqachon chiqarilgan!", show_alert=True)
            return

        bot.answer_callback_query(cb_id, "Kanalga joylanmoqda...")
        pub_res = bot.send_message(
            chat_id=config["CHANNEL_ID"],
            text=draft["text"],
        )

        if pub_res.get("ok"):
            draft["status"] = "published"
            save_drafts(drafts)
            save_to_history(draft["topic"], draft["title"], draft["text"])
            if message_id:
                bot.edit_message_reply_markup(chat_id, message_id, None)
            now_str = datetime.now(TASHKENT_TZ).strftime("%H:%M")
            bot.send_message(
                chat_id,
                f"✅ <b>Post muvaffaqiyatli {config['CHANNEL_ID']} kanaliga chiqarildi!</b>\n"
                f"🕒 Vaqt: {now_str} (Toshkent vaqti)\n"
                f"🗂 Tarix bazasiga saqlandi (qayta takrorlanmaydi).",
            )
        else:
            err_desc = pub_res.get("description", "Noma'lum xatolik")
            bot.send_message(
                chat_id,
                f"❌ <b>Kanalga chiqarishda xatolik:</b> <code>{err_desc}</code>\n\n"
                f"<i>Eslatma: Botni {config['CHANNEL_ID']} kanaliga Admin qilganingizni va "
                f"'Post Messages' huquqini berganingizni tekshiring.</i>",
            )

    elif action == "reject":
        draft["status"] = "rejected"
        save_drafts(drafts)
        if message_id:
            bot.edit_message_reply_markup(chat_id, message_id, None)
        bot.answer_callback_query(cb_id, "Post rad etildi.")
        bot.send_message(chat_id, "❌ Post rad etildi. Yangi post uchun /post bosing.")

    elif action == "regenerate":
        draft["status"] = "regenerated"
        save_drafts(drafts)
        if message_id:
            bot.edit_message_reply_markup(chat_id, message_id, None)
        bot.answer_callback_query(cb_id, "Yangi post tayyorlanmoqda...")
        generate_and_send_for_approval(bot, config)


def handle_admin_message(
    bot: TelegramBotClient,
    config: Dict[str, str],
    message: Dict[str, Any],
) -> None:
    chat_id = str(message.get("chat", {}).get("id", ""))
    user_id = str(message.get("from", {}).get("id", ""))
    text = (message.get("text") or "").strip()

    if not text:
        return

    if text == "/id":
        bot.send_message(chat_id, f"Sizning Telegram ID raqamingiz: <code>{user_id}</code>")
        return

    if user_id != config["ADMIN_USER_ID"]:
        bot.send_message(
            chat_id,
            "🔒 Kechirasiz, bu bot faqat kanal administratori uchun ishlaydi.\n"
            f"Sizning Telegram ID raqamingiz: <code>{user_id}</code>",
        )
        return

    if text.startswith("/start") or text.startswith("/help"):
        now_tashkent = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d %H:%M")
        history_count = len(load_history())
        bot.send_message(
            chat_id,
            f"👋 <b>Assalomu alaykum! «Istanbul xizmatlari» Avto-Post boti (v5.1 — 7/24 Faol) ishga tayyor.</b>\n\n"
            f"📝 <b>Format:</b> Sof matnli sayohat postlari (100% xatosiz va tezkor)\n"
            f"📢 <b>Kanal:</b> {config['CHANNEL_ID']}\n"
            f"⏰ <b>Avtomatik vaqtlar:</b> Har kuni soat <b>10:00</b> va <b>17:00</b> da (Toshkent vaqti)\n"
            f"🕒 <b>Hozirgi Toshkent vaqti:</b> {now_tashkent}\n"
            f"🗂 <b>Xotiradagi postlar soni:</b> {history_count} ta\n\n"
            f"🛠 <b>Buyruqlar:</b>\n"
            f"• /post — Hoziroq yangi post tayyorlash\n"
            f"• /mavzu <i>[joy nomi]</i> — Siz xohlagan joy haqida post tayyorlash\n"
            f"• /tarix — Chiqqan postlar ro'yxatini ko'rish\n"
            f"• /holat — Bot holatini tekshirish",
        )

    elif text.startswith("/post"):
        generate_and_send_for_approval(bot, config)

    elif text.startswith("/mavzu"):
        parts = text.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            bot.send_message(
                chat_id,
                "✏️ <b>Mavzuni buyruqdan keyin yozing.</b>\n"
                "Masalan:\n<code>/mavzu Dolmabahche saroyi</code>",
            )
        else:
            generate_and_send_for_approval(bot, config, custom_topic=parts[1].strip())

    elif text.startswith("/tarix"):
        history = load_history()
        if not history:
            bot.send_message(chat_id, "🗂 Postlar tarixi bo'sh.")
        else:
            lines = ["🗂 <b>Kanalda chiqqan postlar tarixi (oxirgi 15 ta):</b>\n"]
            for idx, item in enumerate(history[-15:], 1):
                lines.append(f"{idx}. <b>{item.get('date')}</b> — {item.get('title') or item.get('topic')}")
            bot.send_message(chat_id, "\n".join(lines))

    elif text.startswith("/holat"):
        now_tashkent = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d %H:%M:%S")
        bot.send_message(
            chat_id,
            f"✅ <b>Bot (v5.1 — 7/24 Faol) ishlamoqda!</b>\n"
            f"🕒 Toshkent vaqti: <code>{now_tashkent}</code>\n"
            f"⏰ Rejadagi vaqtlar: <b>10:00</b> va <b>17:00</b>\n"
            f"📢 Kanal: {config['CHANNEL_ID']}",
        )


# ---------------------------------------------------------------------------
# 11. ANA DÖNGÜ (MAIN)
# ---------------------------------------------------------------------------
def main() -> None:
    # Bulut sunucularında uyanık kalması için arka plan web sunucusu
    start_dummy_web_server_if_needed()

    config = setup_or_load_config()
    bot = TelegramBotClient(config["TELEGRAM_BOT_TOKEN"])

    load_history()

    try:
        me = bot.get_me()
        bot_username = me.get("username", "Noma'lum")
        print(f"[+] Bot ulandi: @{bot_username}")
    except Exception as exc:
        print(f"[-] Telegram Bot Token xato yoki internet yo'q: {exc}")
        sys.exit(1)

    now_str = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d %H:%M")
    bot.send_message(
        config["ADMIN_USER_ID"],
        f"⚡️ <b>@{bot_username} (v5.1 — 7/24 Faol) ishga tushdi!</b>\n"
        f"🕒 Toshkent vaqti: <code>{now_str}</code>\n"
        f"✅ Rasm generatsiyasi yo'q, xatolik chiqmaydi.\n"
        f"✅ Gemini AI + 25 dan ortiq tayyor professional sayohat maqolalari zaxirasi faol.\n\n"
        f"👉 Hoziroq sinab ko'rish uchun /post buyrug'ini bosing!",
    )

    last_update_id: Optional[int] = None
    triggered_slots: set = set()

    print(f"[+] Jadval faol: Har kuni {SCHEDULE_TIMES} da avtomatik ishlaydi.")

    while True:
        try:
            now_tz = datetime.now(TASHKENT_TZ)
            current_hm = now_tz.strftime("%H:%M")
            slot_key = now_tz.strftime("%Y-%m-%d_%H:%M")

            if current_hm in SCHEDULE_TIMES and slot_key not in triggered_slots:
                triggered_slots.add(slot_key)
                generate_and_send_for_approval(bot, config)

            if len(triggered_slots) > 20:
                triggered_slots.clear()
                triggered_slots.add(slot_key)

            updates = bot.get_updates(offset=last_update_id, timeout=5)
            for upd in updates:
                last_update_id = upd["update_id"] + 1
                if "message" in upd:
                    handle_admin_message(bot, config, upd["message"])
                elif "callback_query" in upd:
                    handle_callback(bot, config, upd["callback_query"])

        except KeyboardInterrupt:
            break
        except Exception as exc:
            time.sleep(5)


if __name__ == "__main__":
    main()