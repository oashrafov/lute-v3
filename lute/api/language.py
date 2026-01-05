"""
Languages endpoints
"""

from urllib.parse import urlparse
from flask import Blueprint, request

from sqlalchemy import text as SQLText
from lute.parse.registry import supported_parsers

from lute.db import db
from lute.models.language import Language as LanguageModel
from lute.language.service import Service as LangService

bp = Blueprint("api_languages", __name__, url_prefix="/api/languages")


@bp.route("/", methods=["GET"])
def get_user_languages():
    "get user defined languages"

    sql = """
        select LgID, LgName, LgRightToLeft, book_count, term_count from languages
        left outer join (
        select BkLgID, count(BkLgID) as book_count from books
        group by BkLgID
        ) bc on bc.BkLgID = LgID
        left outer join (
        select WoLgID, count(WoLgID) as term_count from words
        where WoStatus != 0
        group by WoLgID
        ) tc on tc.WoLgID = LgID
        order by LgName
        """

    result = db.session.execute(SQLText(sql)).all()
    languages = [
        {
            "id": row[0],
            "name": row[1],
            "textDirection": "rtl" if row[2] == 1 else "ltr",
            "bookCount": row[3] or 0,
            "termCount": row[4] or 0,
        }
        for row in result
    ]

    return languages, 200


@bp.route("/presets", methods=["GET"])
def get_predefined_languages():
    "get predefined language names only"

    service = LangService(db.session)
    all_predefined = service.supported_predefined_languages()
    existing_langs = db.session.query(LanguageModel).all()
    existing_names = [l.name for l in existing_langs]
    filtered = [p for p in all_predefined if p.name not in existing_names]

    return [language.name for language in filtered]


@bp.route("/", methods=["POST"])
def create_language():
    "Create a predefined language and its stories."

    data = request.get_json()

    if data["loadStories"]:
        service = LangService(db.session)
        lang_id = service.load_language_def(data["name"])

        return {"id": lang_id}, 201

    return {"message": "bad request"}, 400


@bp.route("/presets/<string:langname>", methods=["GET"])
def get_predefined_language(langname):
    "get predefined language form data"

    if langname is None:
        return ""

    service = LangService(db.session)
    predefined = service.supported_predefined_languages()
    candidates = [lang for lang in predefined if lang.name == langname]
    if len(candidates) == 1:
        language = candidates[0]
    else:
        return ""

    return _lang_to_dict(language)


@bp.route("/<int:langid>", methods=["GET"])
def get_user_language(langid):
    """
    get existing language form data
    """

    if not langid:
        return "Language does not exist"

    language = db.session.get(LanguageModel, langid)

    return _lang_to_dict(language)


@bp.route("/parsers", methods=["GET"])
def get_parsers():
    return [{"value": a[0], "label": a[1].name()} for a in supported_parsers()]


@bp.route("/form", methods=["GET"])
def get_language_form():
    """
    default language form settings
    """
    # empty_dict = {
    #     "isActive": True,
    #     "usedFor": "terms",
    #     "type": "embedded",
    #     "url": "",
    #     "label": "",
    #     "hostname": "",
    # }

    return {
        "name": "",
        "characterSubstitutions": "´='|`='|’='|‘='|...=…|..=‥",
        "splitSentencesAt": ".!?",
        "splitSentencesExceptions": "Mr.|Mrs.|Dr.|[A-Z].|Vd.|Vds.",
        "wordCharacters": "a-zA-ZÀ-ÖØ-öø-ȳáéíóúÁÉÍÓÚñÑ",
        "textDirection": "ltr",
        "showPronunciation": False,
        "parserType": "spacedel",
        "dictionaries": [],
    }


def _lang_to_dict(language):
    return {
        "id": language.id,
        "name": language.name,
        "showPronunciation": language.show_romanization,
        "textDirection": "rtl" if language.right_to_left else "ltr",
        "parserType": language.parser_type,
        "characterSubstitutions": language.character_substitutions,
        "splitSentencesAt": language.regexp_split_sentences,
        "splitSentencesExceptions": language.exceptions_split_sentences,
        "wordCharacters": language.word_characters,
        "dictionaries": [
            {
                "id": d.id,
                "usedFor": d.usefor,
                "type": d.dicttype.replace("html", ""),
                "url": (url := d.dicturi),
                "isActive": d.is_active,
                "hostname": (hostname := urlparse(url).hostname),
                "label": (
                    hostname.split("www.")[-1]
                    if hostname and hostname.startswith("www.")
                    else hostname
                ),
            }
            for d in language.dictionaries
        ],
    }
