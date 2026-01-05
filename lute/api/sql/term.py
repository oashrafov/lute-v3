terms = """
      SELECT w.WoID AS WordID,
          LgName,
          L.LgID AS LgID,
          L.LgRightToLeft as LgRightToLeft,
          L.LgParserType as LgParserType,
          w.WoText AS WoText,
          parents.parentlist AS ParentText,
          w.WoTranslation,
          w.WoRomanization,
          WiSource,
          ifnull(tags.taglist, '') AS TagList,
          StText,
          StID,
          StAbbreviation,
          CASE w.WoSyncStatus
              WHEN 1 THEN 'y'
              ELSE ''
          END AS SyncStatus,
          datetime(WoCreated, 'localtime') AS WoCreated
      FROM words w

      INNER JOIN languages L ON L.LgID = w.WoLgID

      INNER JOIN statuses S ON S.StID = w.WoStatus

      LEFT OUTER JOIN
      (SELECT WpWoID AS WoID,
              GROUP_CONCAT(PText, ', ') AS parentlist
      FROM
          (SELECT WpWoID,
                  WoText AS PText
          FROM wordparents wp
          INNER JOIN words ON WoID = WpParentWoID
          ORDER BY WoText) parentssrc
      GROUP BY WpWoID) AS parents ON parents.WoID = w.WoID

      LEFT OUTER JOIN
      (SELECT WtWoID AS WoID,
              GROUP_CONCAT(TgText, ', ') AS taglist
      FROM
          (SELECT WtWoID,
                  TgText
          FROM wordtags wt
          INNER JOIN tags t ON t.TgID = wt.WtTgID
          ORDER BY TgText) tagssrc
      GROUP BY WtWoID) AS tags ON tags.WoID = w.WoID

      LEFT OUTER JOIN wordimages wi ON wi.WiWoID = w.WoID
    """

tags = """SELECT
        TgID,
        TgText,
        TgComment,
        ifnull(TermCount, 0) as TermCount
        FROM tags
        left join (
        select WtTgID,
        count(*) as TermCount
        from wordtags
        group by WtTgID
        ) src on src.WtTgID = TgID
"""
