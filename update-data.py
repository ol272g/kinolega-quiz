#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Обновляет assets/data.js (сохранённую копию данных) из Google Таблицы.

Зачем нужен: сайт умеет тянуть таблицу сам, но только когда он открыт
по http/https (на хостинге). Если index.html открывают двойным кликом
с диска, браузер запрещает такой запрос, и показывается сохранённая копия.
Этот скрипт перезаписывает сохранённую копию свежими данными.

Запуск:  python update-data.py
Нужен только Python 3 (стандартная библиотека, никаких пакетов).
"""

import csv, datetime, io, json, re, sys, urllib.parse, urllib.request
from collections import defaultdict

# Главная таблица: игры, Rating и сезоны — сюда пишет Apps Script («Обновить рейтинги»)
MAIN_ID  = "1NQqMvuNrNAYw5LGvdAS-4lUhnTdf7-U5CZHaIcgv4YU"
# Годовой зачёт KinOlega_2026 есть только в этой таблице
YEAR_ID  = "1D11oDpDLMaRFFTeLwWPOMJ49x8ZVEXSqzyxZsXJf280"
HTML     = "index.html"
DATA_JS  = "assets/data.js"
SEASONS  = ["Зима_2026", "Весна_2026", "Лето_2026"]


def fetch(sheet, sheet_id=MAIN_ID):
    url = ("https://docs.google.com/spreadsheets/d/%s/gviz/tq?tqx=out:csv&sheet=%s"
           % (sheet_id, urllib.parse.quote(sheet)))
    with urllib.request.urlopen(url, timeout=60) as r:
        text = r.read().decode("utf-8")
    rows = list(csv.reader(io.StringIO(text)))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if len(rows) < 2:
        raise RuntimeError("лист «%s» пуст" % sheet)
    return [c.strip() for c in rows[0]], rows[1:]


def num(v):
    if v is None:
        return None
    s = re.sub(r"[\s  ]", "", str(v)).replace(",", ".")
    if s in ("", "-"):
        return None
    try:
        return round(float(s), 2)
    except ValueError:
        return None


SUP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")


def qcell(v):
    """Ячейка вопроса «300 ⁰⋅⁴⁵»: [очки / 50, вес × 100] — как на сайте."""
    m = re.match(r"^([\d\s\u00a0\u202f]+?)\s*([⁰¹²³⁴⁵⁶⁷⁸⁹]+)⋅([⁰¹²³⁴⁵⁶⁷⁸⁹]+)$", str(v or "").strip())
    if not m:
        return [0, 0]
    points = int(re.sub(r"\D", "", m.group(1)) or 0)
    weight = float(m.group(2).translate(SUP) + "." + m.group(3).translate(SUP))
    return [points // 50, int(round(weight * 100))]


def iso(v):
    s = str(v or "").strip()
    m = re.match(r"^(\d{2})\.(\d{2})\.(\d{4})$", s)
    if m:
        return "%s-%s-%s" % (m.group(3), m.group(2), m.group(1))
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    return m.group(0) if m else None


def col(head, name):
    try:
        return head.index(name)
    except ValueError:
        raise RuntimeError("нет колонки «%s» (есть: %s)" % (name, ", ".join(head)))


def build():
    # --- игры ---
    head, rows = fetch("KinOlega_игрыG")
    c = lambda n: col(head, n)
    bucket = {}
    for r in rows:
        player = r[c("Player")].strip()
        if not player:
            continue
        paket, ngame = r[c("Paket")].strip(), num(r[c("#Game")])
        key = (paket, ngame)
        bucket.setdefault(key, {"paket": paket, "n": ngame, "date": iso(r[c("Date")]), "players": []})
        bucket[key]["players"].append({
            "p": player, "pts": num(r[c("Points")]),
            "r": num(r[c("Rating")]), "nr": num(r[c("nRating")]),
        })
    games = list(bucket.values())
    for g in games:
        g["players"].sort(key=lambda p: (p["pts"] is None, -(p["pts"] or 0)))
        for i, p in enumerate(g["players"]):
            p["pos"] = i + 1
    games.sort(key=lambda g: (g["date"] or "", g["paket"], g["n"] or 0))

    # --- рейтинг ---
    head, rows = fetch("Rating")
    c = lambda n: col(head, n)
    paket_cols = [(i, h) for i, h in enumerate(head) if h.startswith("KinOlega#")]
    rating = []
    for r in rows:
        if not r[c("PLAYER")].strip():
            continue
        rating.append({
            "rank": num(r[c("RANK")]), "p": r[c("PLAYER")].strip(), "r": num(r[c("RATING")]),
            "w": num(r[c("WINS")]), "g": num(r[c("GAMES")]), "avgP": num(r[c("avg_P")]),
            "avgO": num(r[c("avg_P_opp")]), "miss": num(r[c("MISSED")]),
            "hist": [{"paket": h, "r": num(r[i])} for i, h in paket_cols if num(r[i]) is not None],
        })

    # --- годовой зачёт ---
    head, rows = fetch("KinOlega_2026", YEAR_ID)
    c = lambda n: col(head, n)
    year = [{"pos": num(r[c("Место")]), "p": r[c("Имя")].strip(),
             "pts": num(r[c("tОчки")]), "pen": num(r[c("Штраф")])}
            for r in rows if r[c("Имя")].strip()]

    # --- сезоны ---
    seasons = []
    for name in SEASONS:
        head, rows = fetch(name)
        c = lambda n: col(head, n)
        qcols = [i for i, h in enumerate(head) if re.match(r"^Q\d+$", h)]
        cell = lambda r, i: r[i] if i < len(r) else ""
        seasons.append({
            "name": name.replace("_", " "), "key": name,
            "items": [{"date": iso(r[c("Дата игры")]), "game": r[c("Игра")],
                       "pos": num(r[c("Место")]), "p": r[c("Имя игрока")].strip(),
                       "f": num(r[c("fОчки")]), "pts": num(r[c("Очки")]),
                       "ans": num(r[c("Ответы")]), "w": num(r[c("wОчки")]),
                       "qn": [qcell(cell(r, i))[0] for i in qcols],
                       "qw": [qcell(cell(r, i))[1] for i in qcols]}
                      for r in rows if r[c("Имя игрока")].strip()],
        })

    return {"updated": datetime.date.today().isoformat(), "games": games,
            "rating": rating, "year": year, "seasons": seasons}


def main():
    print("Загружаю данные из Google Таблицы…")
    data = build()
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    # данные не изменились — ничего не перезаписываем (иначе автообновление делало бы пустые коммиты)
    try:
        with io.open(DATA_JS, encoding="utf-8") as f:
            m = re.search(r"window\.KINOLEGA_SNAPSHOT = (.*);\s*$", f.read(), re.S)
        old = json.loads(m.group(1)) if m else None
    except (OSError, ValueError):
        old = None
    without_date = lambda d: {k: v for k, v in d.items() if k != "updated"}
    if old is not None and without_date(old) == without_date(data):
        print("Данные в таблице не изменились — файлы не трогаю.")
        return 0

    with io.open(DATA_JS, "w", encoding="utf-8") as f:
        f.write("/* Данные KinOlega Quiz — файл перезаписывает update-data.py */\n"
                "window.KINOLEGA_SNAPSHOT = " + payload + ";\n")

    # новая метка версии в index.html — браузеры не покажут устаревшую копию из кэша
    stamp = datetime.datetime.now().strftime("%Y%m%d%H%M")
    with io.open(HTML, encoding="utf-8") as f:
        html = f.read()
    new, count = re.subn(r'assets/data\.js\?v=[^"]*"', 'assets/data.js?v=%s"' % stamp, html, count=1)
    if count != 1:
        print("Не нашёл подключение assets/data.js в %s" % HTML)
        return 1
    with io.open(HTML, "w", encoding="utf-8") as f:
        f.write(new)

    print("Готово. Игр: %d · игроков в рейтинге: %d · сезонов: %d"
          % (len(data["games"]), len(data["rating"]), len(data["seasons"])))
    print("Обновлено: %s" % data["updated"])
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print("Ошибка: %s" % e)
        sys.exit(1)
