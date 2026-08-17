# this_file: milkwashy/src/milkwashy/indata.py
"""Authored long-form seed texts in four languages.

Authored directly (not model-generated) to avoid a chicken-and-egg dependency
on the pipeline. What matters here is length and sentence-boundary variety, not
literary merit. Language codes are ISO 639-1 as used by sentencex.
"""

from __future__ import annotations

from pathlib import Path

# language code -> (filename stem, long text)
TEXTS: dict[str, tuple[str, str]] = {
    "en": (
        "en-rivers-and-machines",
        """The old mill stood at the bend of the river, where the water slowed and
turned a deep, patient green. For nearly two centuries it had ground the wheat of
three villages, and its great wheel had never once stopped for longer than a
frozen winter. People said the miller could read the weather in the sound of the
current. When the river ran high and loud, he closed the sluice early; when it
whispered, he let the stones turn through the night. Machines, he liked to say,
are only as clever as the hands that feed them.

Today the mill is a museum, and children press their faces to the glass to watch
the restored wheel creak into motion. The guides explain how the gears multiply a
slow push into a fast, useful turning, and how a single shaft can drive a dozen
tools at once. It is a small lesson in leverage, but it lingers. Long before
anyone spoke of automation, this building already knew that patience and geometry
could do the work of many arms. The river, indifferent as ever, keeps rolling
past the door. It does not care whether it grinds flour or spins a turbine, and
perhaps that indifference is the point: the same current, harnessed differently,
becomes bread in one century and electricity in the next.""",
    ),
    "pl": (
        "pl-rzeki-i-maszyny",
        """Stary młyn stał w zakolu rzeki, tam gdzie woda zwalniała i przybierała
głęboką, cierpliwą zieleń. Przez blisko dwa stulecia mełł pszenicę trzech wsi, a
jego wielkie koło ani razu nie zatrzymało się na dłużej niż na czas zamarzniętej
zimy. Mówiono, że młynarz potrafił odczytać pogodę z szumu nurtu. Gdy rzeka
płynęła wysoko i głośno, wcześnie zamykał śluzę; gdy szeptała, pozwalał kamieniom
obracać się przez całą noc. Maszyny, lubił powtarzać, są tylko tak sprytne, jak
ręce, które je karmią.

Dziś młyn jest muzeum, a dzieci przyciskają twarze do szyby, żeby patrzeć, jak
odrestaurowane koło ze skrzypieniem rusza z miejsca. Przewodnicy tłumaczą, jak
przekładnie zamieniają powolne pchnięcie w szybki, użyteczny obrót i jak jeden
wał może napędzać tuzin narzędzi naraz. To niewielka lekcja o dźwigni, ale
zostaje w pamięci. Na długo zanim ktokolwiek mówił o automatyzacji, ten budynek
już wiedział, że cierpliwość i geometria potrafią wykonać pracę wielu ramion.
Rzeka, obojętna jak zawsze, wciąż płynie obok drzwi. Nie obchodzi jej, czy miele
mąkę, czy kręci turbiną, i być może właśnie ta obojętność jest sednem sprawy.""",
    ),
    "de": (
        "de-fluesse-und-maschinen",
        """Die alte Mühle stand in der Flussbiegung, wo das Wasser langsamer wurde
und ein tiefes, geduldiges Grün annahm. Fast zwei Jahrhunderte lang hatte sie den
Weizen dreier Dörfer gemahlen, und ihr großes Rad hatte nie länger als einen
gefrorenen Winter stillgestanden. Man sagte, der Müller könne das Wetter am
Klang der Strömung ablesen. Wenn der Fluss hoch und laut lief, schloss er früh
das Wehr; wenn er flüsterte, ließ er die Steine die ganze Nacht drehen. Maschinen,
pflegte er zu sagen, sind nur so klug wie die Hände, die sie füttern.

Heute ist die Mühle ein Museum, und Kinder drücken ihre Gesichter an die Scheibe,
um zuzusehen, wie sich das restaurierte Rad knarrend in Bewegung setzt. Die
Führer erklären, wie die Zahnräder einen langsamen Schub in eine schnelle,
nützliche Drehung verwandeln und wie eine einzige Welle ein Dutzend Werkzeuge
zugleich antreiben kann. Es ist eine kleine Lektion über Hebelwirkung, aber sie
bleibt haften. Lange bevor jemand von Automatisierung sprach, wusste dieses
Gebäude bereits, dass Geduld und Geometrie die Arbeit vieler Arme verrichten
können. Der Fluss, gleichgültig wie eh und je, rollt weiter an der Tür vorbei.""",
    ),
    "ar": (
        "ar-anhar-wa-alat",
        """كانت الطاحونة القديمة تقف عند منعطف النهر، حيث يتباطأ الماء ويكتسب لونًا
أخضر عميقًا صبورًا. لما يقرب من قرنين، طحنت قمح ثلاث قرى، ولم تتوقف عجلتها
الكبيرة يومًا أطول من شتاء متجمد. كان الناس يقولون إن الطحّان يستطيع أن يقرأ
الطقس في صوت التيار. حين يجري النهر عاليًا صاخبًا، كان يغلق الهويس مبكرًا؛ وحين
يهمس، كان يترك الأحجار تدور طوال الليل. والآلات، كان يحب أن يقول، ليست أذكى من
الأيدي التي تطعمها.

أما اليوم فقد صارت الطاحونة متحفًا، ويلصق الأطفال وجوههم بالزجاج ليشاهدوا العجلة
المرمّمة وهي تتحرك بصريرها. يشرح المرشدون كيف تضاعف التروس دفعة بطيئة لتصير دورانًا
سريعًا نافعًا، وكيف يمكن لعمود واحد أن يحرّك عشرات الأدوات في آنٍ معًا. إنه درس
صغير في الرافعة، لكنه يبقى في الذهن. قبل أن يتحدث أحد عن الأتمتة بزمن طويل، كان
هذا المبنى يعرف أن الصبر والهندسة قادران على أداء عمل أذرع كثيرة. والنهر، لا مبالٍ
كعادته، ما زال يتدفق أمام الباب، لا يعنيه أيطحن دقيقًا أم يدير عنفة.""",
    ),
}


def write_indata(indata_dir: Path) -> list[tuple[str, Path]]:
    """Write each seed text to `<indata_dir>/<lang>__<stem>.txt`.

    Returns a list of (language_code, path).
    """
    indata_dir.mkdir(parents=True, exist_ok=True)
    written: list[tuple[str, Path]] = []
    for lang, (stem, text) in TEXTS.items():
        # normalise the soft-wrapped source into flowing paragraphs
        paras = [" ".join(p.split()) for p in text.strip().split("\n\n")]
        body = "\n\n".join(paras)
        path = indata_dir / f"{lang}__{stem}.txt"
        path.write_text(body + "\n", encoding="utf-8")
        written.append((lang, path))
    return written
