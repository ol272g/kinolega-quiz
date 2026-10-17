#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Размечает вопросы сезонных пакетов (.siq из SIGame) и пишет assets/packs.js.

В файл попадает только «карта» вопроса — формат, тип ответа и ступень сложности.
Ни текстов вопросов, ни ответов, ни названий тем там нет, поэтому спойлеров на сайте не будет.
Порядок вопросов совпадает с колонками Q1…Qn в листах сезонов.

Запуск (пакеты лежат только у организатора):
    python build-packs.py            # пути по умолчанию — в PACKS ниже
    python build-packs.py --check    # вывести разметку для проверки глазами

Новый сезон: добавить его .siq в PACKS и запустить скрипт ещё раз.
"""

import json, re, sys, zipfile
import xml.etree.ElementTree as ET

ROOT = r"D:\Своя Игра\KinOlega_Project\KinOlega_Open#1"
PACKS = {
    "Зима_2026":  ROOT + r"\Зима\KinOlega_winter_O1.siq",
    "Весна_2026": ROOT + r"\Весна\KinOlega Open#1_2.siq",
    "Лето_2026":  ROOT + r"\Лето\KinOlega_summer_O1.siq",
    "Осень_2026": ROOT + r"\Осень\KinOlega_Осень.siq",
}
OUT = "assets/packs.js"

CATS = ["Фильм", "Сериал / мультфильм", "Актёр / режиссёр", "Слово / понятие", "Несколько ответов"]
FMTS = ["Текст", "Кадр"]
FILM, SERIES, PERSON, WORD, MULTI = range(5)
CARTOON = SERIES   # мультфильмы и сериалы — одна категория: по отдельности вопросов слишком мало

# Темы, где тип ответа нельзя понять по самому ответу: (сезон, номер первого вопроса темы) -> категория
# SOFT — подсказка только для ответов без «(Eng, год)»: если в такой теме попался фильм, он остаётся фильмом
SOFT = {("Весна_2026", 16)}
OVERRIDE = {
    ("Зима_2026", 31): MULTI,     # На голове: предмет на голове + фильм
    ("Зима_2026", 46): WORD,      # Психологические эффекты
    ("Весна_2026", 1): CARTOON,   # Мультипёсики
    ("Весна_2026", 16): WORD,     # Деревья и растения
    ("Весна_2026", 21): MULTI,    # Режиссёр на замену: режиссёр + актёр + фильм
    ("Весна_2026", 41): PERSON,   # Актёры в картинках
    ("Весна_2026", 51): WORD,     # Лишний город
    ("Осень_2026", 16): CARTOON,  # Стилизованные кроксы
    ("Осень_2026", 26): MULTI,    # Радужная любовь: актёр + фильм
    ("Осень_2026", 36): SERIES,   # Сериальные ассоциации
    ("Осень_2026", 41): SERIES,   # Дорамы
}

WORK = re.compile(r"\([^\n]*\b(?:19|20)\d{2}\b[^\n]*\)")          # «Название (Eng, 2009)»
SERIES_YEARS = re.compile(r"\b(?:19|20)\d{2}\s*[—–-]")               # «(…, 2002 — 2008)»
PARTICLES = {"фон", "де", "ван", "ди", "дель", "да", "ле", "ла", "мл."}


def looks_like_person(answer):
    """Без года в скобках: «Ленни Кравиц», «Ларс фон Триер» — 2–3 слова с заглавных."""
    head = re.split(r"\s*\(", answer, 1)[0].strip()
    words = head.split()
    if not 2 <= len(words) <= 3 or re.search(r"\d|;", head) or len({w.lower() for w in words}) < len(words):
        return False
    return all(w[0].isupper() or w.lower() in PARTICLES for w in words)


def read(path):
    xml = zipfile.ZipFile(path).read("content.xml").decode("utf-8-sig")
    root = ET.fromstring(re.sub(r' xmlns="[^"]+"', "", xml, 1))
    out = []
    for ri, rd in enumerate(root.iter("round")):
        for th in rd.iter("theme"):
            qs = []
            for q in th.iter("question"):
                media = {it.get("type") or "text" for p in q.iter("param") if p.get("name") == "question" for it in p.iter("item")}
                ans = " / ".join((a.text or "").strip() for a in q.iter("answer"))
                qs.append({"image": "image" in media, "answer": ans})
            out.append({"round": ri + 1, "theme": th.get("name") or "", "qs": qs})
    return out


def classify(season, themes):
    rows, n = [], 0
    for th in themes:
        forced = OVERRIDE.get((season, n + 1))
        for j, q in enumerate(th["qs"]):
            n += 1
            a = q["answer"]
            if th["round"] >= 4:
                cat, tier = WORD, 0                                  # финал: «Про …» — ответ всегда слово или выражение
            else:
                tier = j + 1
                if forced is not None and not ((season, n - j) in SOFT and WORK.search(a)):
                    cat = forced
                elif WORK.search(a):
                    cat = SERIES if SERIES_YEARS.search(a) else FILM
                elif looks_like_person(a):
                    cat = PERSON
                else:
                    cat = WORD
            rows.append((cat, 1 if q["image"] else 0, tier))
    return rows


def main():
    packs = {k: classify(k, read(p)) for k, p in PACKS.items()}
    if "--check" in sys.argv:
        for k, p in PACKS.items():
            n = 0
            for th in read(p):
                for q in th["qs"]:
                    n += 1
                    cat, fmt, tier = packs[k][n - 1]
                    print(f"{k} Q{n:02d} r{th['round']} t{tier} {FMTS[fmt]:5} {CATS[cat]:18} | {q['answer'][:60]}")
        return
    body = {k: [list(r) for r in v] for k, v in packs.items()}
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("// Разметка вопросов сезонных пакетов: [категория, формат, ступень]. Без текстов вопросов и ответов.\n")
        f.write("// Сгенерировано build-packs.py\n")
        f.write("window.KINOLEGA_PACKS = " + json.dumps({"cats": CATS, "fmts": FMTS, "packs": body}, ensure_ascii=False, separators=(",", ":")) + ";\n")
    for k, v in packs.items():
        from collections import Counter
        c = Counter(CATS[r[0]] for r in v)
        print(k, len(v), dict(c))


if __name__ == "__main__":
    main()
