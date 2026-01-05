"Book endpoints"

import os
import json
from datetime import datetime

from flask import Blueprint, jsonify, send_file, current_app, request
from sqlalchemy import text as SQLText

from lute.db import db
from lute.models.book import Text, Book as BookModel
from lute.models.repositories import BookRepository
from lute.book.model import Book, Repository
from lute.book.service import (
    Service as BookService,
    BookImportException,
    FileTextExtraction,
)
from lute.read.service import Service as ReadService
from lute.read.render.service import Service as RenderService
from lute.book.stats import Service as StatsService
from lute.utils.data_tables import supported_parser_type_criteria
from lute.api.utils.utils import get_filter, parse_url_params
from lute.api.sql.book import books as base_sql


bp = Blueprint("api_books", __name__, url_prefix="/api/books")


@bp.route("/", methods=["GET", "POST"])
def books():
    "get books list or create a new book"
    if request.method == "POST":
        return create_book()

    return get_books()


def create_book():
    """
    create new book
    """
    data = request.form
    data = {k: None if v == "undefined" else v for k, v in data.items()}
    files_dict = request.files.to_dict()

    book = Book()

    try:
        book_service = BookService()

        book.title = data["title"]
        book.text = data["text"]
        book.language_id = data["languageId"]
        book.source_uri = data["source"]
        book.book_tags = data["tags"]
        book.threshold_page_tokens = int(data["wordsPerPage"])
        book.split_by = data["splitBy"]

        audio_file = files_dict.get("audioFile", None)
        if audio_file:
            if audio_file.filename is None:
                raise BookImportException("Must set audio name")
            new_name = book_service.unique_fname(audio_file.filename)
            fp = os.path.join(current_app.env_config.useraudiopath, new_name)
            with open(fp, mode="wb") as fcopy:  # Use "wb" to write in binary mode
                while chunk := audio_file.stream.read(
                    8192
                ):  # Read the stream in chunks (e.g., 8 KB)
                    fcopy.write(chunk)
            book.audio_filename = new_name

        repo = Repository(db.session)

        dbbook = repo.add(book)
        repo.commit()

        return {
            "id": dbbook.id,
            "title": dbbook.title,
            "languageId": dbbook.language.id,
        }, 201

    except BookImportException as e:
        return e.message, 400


def get_books():
    "Get all books applying filters and sorting"

    start, size, filters, filter_modes, global_filter, sorting = parse_url_params(
        request
    )

    where = [f"WHERE LgParserType in ({ supported_parser_type_criteria() })"]
    shelf = request.args.get("shelf", "active")
    if shelf == "active":
        where.append(" AND BkArchived != TRUE")
    elif shelf == "archived":
        where.append(" AND BkArchived = TRUE")

    fields = {
        "title": {"num": False, "column": "BkTitle"},
        "languageName": {"num": False, "column": "LgName"},
        "tags": {"num": False, "column": "TagList"},
        "wordCount": {"num": True, "column": "WordCount"},
        "status": {"num": True, "column": "UnknownPercent"},
        "lastRead": {"num": False, "column": "LastOpenedDate"},
    }

    # Apply Filters
    for flt in filters:
        field = flt.get("id")
        value = flt.get("value", "").strip()
        mode = filter_modes.get(field, "contains")

        where.append(
            get_filter(mode, fields[field]["column"], value, fields[field]["num"])
        )

    # Apply Global Filter
    if global_filter:
        if global_filter.isdigit():
            where.append(
                f""" AND (BkTitle LIKE '%{global_filter}%' OR
                            LgName LIKE '%{global_filter}%' OR
                            WordCount = {global_filter} OR
                            UnknownPercent = {global_filter}
                        )"""
            )
        else:
            where.append(
                f""" AND (
                            BkTitle LIKE '%{global_filter}%' OR
                            LgName LIKE '%{global_filter}%'
                        )"""
            )
    # Apply Sorting
    order_by = ""
    if sorting:
        sort_clauses = []
        for sort in sorting:
            field = sort.get("id")
            desc_order = sort.get("desc", False)

            sort_clauses.append(
                f"{fields[field]['column']} {'DESC' if desc_order else 'ASC'} NULLS LAST"
            )

        # Add the ORDER BY clause
        if sort_clauses:
            order_by = " ORDER BY " + ", ".join(sort_clauses)

    # Apply Pagination
    limit = ""
    if size != -1:
        limit = f" LIMIT {size} OFFSET {start}"

    realbase = f"({base_sql}) realbase".replace("\n", " ")
    filtered = f"SELECT COUNT(*) FROM {realbase} {' '.join(where)}"
    archived = """
                SELECT COUNT(*) AS ArchivedBookCount
                FROM books
                WHERE BkArchived = 1
                """
    total = """
            SELECT COUNT(*) AS TotalBookCount
            FROM books
            """

    filtered_count = db.session.execute(SQLText(filtered)).scalar()
    archived_count = db.session.execute(SQLText(archived)).scalar() or 0
    total_count = db.session.execute(SQLText(total)).scalar()
    active_count = total_count - archived_count

    final_query = f"{base_sql} {' '.join(where)} {order_by} {limit}"
    results = db.session.execute(SQLText(final_query)).fetchall()

    books_list = []
    for row in results:
        books_list.append(_book_row_to_dict(row))

    pinned = json.loads(request.args.get("pinned", '{"top": [], "bottom": []}'))
    pinned_ids = pinned["top"] + pinned["bottom"]
    pinned_books = _get_pinned_books(pinned_ids)

    books_list.extend(pinned_books)

    return {
        "data": books_list,
        "totalCount": total_count,
        "filteredCount": filtered_count,
        "activeCount": active_count,
        "archivedCount": archived_count,
    }


@bp.route("/<int:bookid>", methods=["GET"])
def get_book(bookid):
    "get book"

    book = _find_book(bookid)
    if book is None:
        return jsonify("No such book"), 404

    page_num = 1
    text = book.texts[0]
    if book.current_tx_id:
        text = db.session.get(Text, book.current_tx_id)
        page_num = text.order

    book_dict = {
        "id": book.id,
        "title": book.title,
        "source": book.source_uri or None,
        "pageCount": book.page_count,
        "currentPage": page_num,
        "languageId": book.language.id,
        "textDirection": "rtl" if book.language.right_to_left else "ltr",
        "audio": (
            {
                "id": book.id,
                "name": book.audio_filename,
                "position": (
                    float(book.audio_current_pos) if book.audio_current_pos else 0
                ),
                "bookmarks": (
                    [float(x) for x in book.audio_bookmarks.split(";")]
                    if book.audio_bookmarks
                    else []
                ),
            }
            if book.audio_filename
            else None
        ),
        # mock bookmarks
        "bookmarks": [
            {
                "page": 2,
                "sentences": [
                    {
                        "id": 2,
                        "description": "description_2",
                    },
                    {"id": 6, "description": "description_6"},
                    {"id": 8, "description": "description_8"},
                ],
            },
        ],
    }

    return book_dict


@bp.route("/<int:bookid>", methods=["PATCH"])
def edit_book(bookid):
    "Edit a book"

    data = request.form
    data = {k: None if v == "undefined" else v for k, v in data.items()}

    action = data.get("action")
    if action in ("archive", "unarchive"):
        book = _find_book(bookid)
        book.archived = action == "archive"

        db.session.add(book)
        db.session.commit()
        archived_count = (
            db.session.query(BookModel).filter(BookModel.archived == 1).count()
        )

        response = {"id": book.id, "title": book.title}
        response["archivedCount"] = archived_count
        return response, 200

    if action == "edit":
        files_dict = request.files.to_dict()
        repo = Repository(db.session)
        book = repo.load(bookid)

        for key, value in data.items():
            if hasattr(book, key):
                setattr(book, key, value)

        audio_file = files_dict.get("audio_file", None)
        if audio_file:
            setattr(book, "audio_stream", audio_file.stream)
            setattr(book, "audio_stream_filename", audio_file.filename)

        svc = BookService()
        svc.import_book(book, db.session)

        return {"id": book.id, "title": book.title}, 200

    if action == "updateAudioData":
        book = _find_book(bookid)
        position = data.get("position")
        bookmarks = data.get("bookmarks")

        if position:
            book.audio_current_pos = float(position)
        if bookmarks:
            book.audio_bookmarks = bookmarks

        if position or bookmarks:
            db.session.add(book)
            db.session.commit()

        return {"id": book.id, "title": book.title}, 200

    if action == "markPageAsRead":
        pagenum = data.get("page")
        mark_rest_as_known = data.get("markRestAsKnown", False)

        service = ReadService(db.session)
        service.mark_page_read(bookid, pagenum, mark_rest_as_known)

        return {"id": book.id, "title": book.title}, 200

    return "", 400


@bp.route("/<int:bookid>", methods=["DELETE"])
def delete_book(bookid):
    "delete a book."

    b = _find_book(bookid)

    db.session.delete(b)
    db.session.commit()

    return {"title": b.title}, 200


@bp.route("/parse/url", methods=["POST"])
def parse_content_from_url():
    "Get data for a new book, or flash an error if can't parse."
    service = BookService()
    url = request.data.decode("utf-8")
    try:
        b = service.book_data_from_url(url)
    except BookImportException as e:
        return e.message, 400

    return {"title": b.title, "source": b.source_uri, "text": b.text}


@bp.route("/parse/file", methods=["POST"])
def parse_file_contents():
    "parse file"

    files_dict = request.files.to_dict()
    fte = FileTextExtraction()

    file = files_dict.get("file", None)
    text = ""
    if file:
        text = fte.get_file_content(file.filename, file.stream)

    return {"text": text}


@bp.route("/<int:bookid>/pages/<int:pagenum>", methods=["GET"])
def get_page_content(bookid, pagenum):
    "get page content"
    book = _find_book(bookid)
    if book is None:
        return jsonify("No such book"), 404

    text, paragraphs = _load_page_content(book, pagenum)

    return {"text": text.text, "paragraphs": _paragraphs_to_dict_array(paragraphs)}


@bp.route("/<int:bookid>/pages/<int:pagenum>", methods=["POST"])
def commit_page(bookid, pagenum):
    "commit page to db"

    book = _find_book(bookid)
    if book is None:
        return jsonify("No such book"), 404

    text = book.text_at_page(pagenum)

    should_track = request.get_json().get("shouldTrack", True)
    _commit_session(book, text, should_track)

    _, paragraphs = _load_page_content(book, pagenum)
    read_service = ReadService(db.session)
    read_service._save_new_status_0_terms(paragraphs)  # pylint: disable=W0212

    return {"id": book.id}, 200


@bp.route("<int:bookid>/audio", methods=["GET"])
def get_audio(bookid):
    "Serve the audio, no caching."
    dirname = current_app.env_config.useraudiopath
    br = BookRepository(db.session)
    book = br.find(bookid)
    fname = os.path.join(dirname, book.audio_filename)
    try:
        return send_file(fname, as_attachment=True, max_age=0)
    except FileNotFoundError:
        return (
            jsonify(
                {
                    "error": "Audio file not found: {}".format(
                        fname.rsplit("useraudio\\")[-1]
                    )
                }
            ),
            404,
        )


@bp.route("/<int:bookid>/stats", methods=["GET"])
def get_stats(bookid):
    "Calc stats for the book using the status distribution."
    book = _find_book(bookid)
    svc = StatsService(db.session)
    status_distribution = svc.calc_status_distribution(book)

    sum_words = sum(status_distribution.values())
    if sum_words == 0:
        return ""

    status_distribution[99] = status_distribution.get(98, 0) + status_distribution.get(
        99, 0
    )
    status_distribution.pop(98, "")

    return [
        {
            "status": status,
            "wordCount": words,
            "percentage": words / sum_words * 100,
        }
        for status, words in status_distribution.items()
    ]


@bp.route("/form", methods=["GET"])
def get_new_book_form():
    return {
        "title": "",
        "text": "",
        "languageId": None,
        "importUrl": "",
        "textFile": None,
        "audioFile": None,
        "wordsPerPage": 250,
        "splitBy": "paragraphs",
        "source": "",
        "tags": [],
    }


def _find_book(bookid):
    "Find book from db."
    br = BookRepository(db.session)
    return br.find(bookid)


def _commit_session(dbbook, text, track_page_open=False):
    "commit current page"

    if track_page_open:
        text.start_date = datetime.now()
        dbbook.current_tx_id = text.id

    db.session.add(dbbook)
    db.session.add(text)
    db.session.commit()


def _load_page_content(dbbook, pagenum):
    "get raw text and paragraphs"

    text = dbbook.text_at_page(pagenum)
    text.load_sentences()
    lang = text.book.language
    rs = RenderService(db.session)
    paragraphs = rs.get_paragraphs(text.text, lang)

    return text, paragraphs


def _get_pinned_books(ids):
    books_list = []
    if ids:
        ids_tuple = tuple(ids) if len(ids) > 1 else tuple([ids[0], ids[0]])
        query = f"{base_sql} WHERE books.BkID IN {ids_tuple}"
        result = db.session.execute(SQLText(query)).fetchall()

        for row in result:
            books_list.append(_book_row_to_dict(row))

    return books_list


def _book_row_to_dict(row):
    return {
        "id": row.BkID,
        "languageName": row.LgName,
        "languageId": row.BkLgID,
        "textDirection": "rtl" if row.LgRightToLeft == 1 else "ltr",
        "source": row.BkSourceURI or None,
        "audioName": row.BkAudioFilename or None,
        "title": row.BkTitle,
        "wordCount": row.WordCount,
        "pageCount": row.PageCount,
        "currentPage": row.PageNum,
        "tags": row.TagList.split(",") if row.TagList else [],
        "isCompleted": row.IsCompleted == 1,
        "unknownPercent": row.UnknownPercent,
        "isArchived": row.BkArchived == 1,
        "lastRead": row.LastOpenedDate,
    }


def _paragraphs_to_dict_array(paragraphs):
    return [
        [
            [
                {
                    "id": textitem.span_id,
                    "displayText": textitem.html_display_text,
                    "languageId": getattr(textitem, "lang_id", None),
                    "paragraphId": textitem.paragraph_number,
                    "sentenceId": textitem.sentence_number,
                    "text": textitem.text,
                    "order": textitem.index,
                    "wordId": textitem.wo_id,
                    "isWord": textitem.is_word,
                    "status": textitem.wo_status,
                    "isOverlapped": textitem.is_overlapped,
                    "isSentenceStart": textitem.is_sentence_start,
                    "isSentenceEnd": textitem.is_sentence_end,
                }
                for textitem in sentence
            ]
            for sentence in paragraph
        ]
        for paragraph in paragraphs
    ]
