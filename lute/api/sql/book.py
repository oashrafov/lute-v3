books = """
    SELECT
        books.BkID As BkID,
        LgName,
        languages.LgRightToLeft as LgRightToLeft,
        languages.LgParserType as LgParserType,
        BkLgID,
        BkSourceURI,
        BkTitle,
        BkAudioFilename,
        CASE WHEN currtext.TxID IS null then 1 else currtext.TxOrder END AS PageNum,
        textcounts.pagecount AS PageCount,
        booklastopened.lastopeneddate AS LastOpenedDate,
        BkArchived,
        tags.taglist AS TagList,
        textcounts.wc AS WordCount,
        bookstats.distinctterms AS DistinctCount,
        bookstats.distinctunknowns AS UnknownCount,
        bookstats.unknownpercent AS UnknownPercent,
        bookstats.status_distribution AS StatusDistribution,
        CASE WHEN completed_books.BkID IS null then 0 else 1 END AS IsCompleted
    FROM books

    INNER JOIN languages ON LgID = books.BkLgID

    LEFT OUTER JOIN texts currtext ON currtext.TxID = BkCurrentTxID

    INNER JOIN (
        select TxBkID, max(TxStartDate) as lastopeneddate from texts group by TxBkID
    ) booklastopened on booklastopened.TxBkID = books.BkID

    INNER JOIN (
        SELECT TxBkID, SUM(TxWordCount) AS wc, COUNT(TxID) AS pagecount
        FROM texts
        GROUP BY TxBkID
    ) textcounts ON textcounts.TxBkID = books.BkID

    LEFT OUTER JOIN bookstats ON bookstats.BkID = books.BkID

    LEFT OUTER JOIN (
        SELECT BtBkID AS BkID, GROUP_CONCAT(T2Text, ', ') AS taglist
        FROM (
            SELECT BtBkID, T2Text
            FROM booktags bt
            INNER JOIN tags2 t2 ON t2.T2ID = bt.BtT2ID
            ORDER BY T2Text
        ) tagssrc
        GROUP BY BtBkID
    ) AS tags ON tags.BkID = books.BkID

    LEFT OUTER JOIN (
        SELECT texts.TxBkID AS BkID
        FROM texts
        INNER JOIN (
            /* last page in each book */
            select TxBkID, max(TxOrder) AS maxTxOrder FROM texts GROUP BY TxBkID
        ) last_page ON last_page.TxBkID = texts.TxBkID AND last_page.maxTxOrder = texts.TxOrder
        WHERE TxReadDate IS NOT null
    ) completed_books ON completed_books.BkID = books.BkID
"""
