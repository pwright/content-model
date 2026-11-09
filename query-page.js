(function () {
  var container = document.getElementById("query-app");
  if (!container) return;

  var REPORTS = [
    {
      id: "coverage-summary",
      title: "Coverage Summary",
      description: "Total topics, mappings, and coverage percentages",
      category: "summary",
      sql:
        "SELECT " +
        "(SELECT COUNT(*) FROM UpstreamTopic) AS upstream_total, " +
        "(SELECT COUNT(*) FROM DownstreamTopic) AS downstream_total, " +
        "(SELECT COUNT(*) FROM ContentMapping) AS mapping_total, " +
        "ROUND(100.0 * (SELECT COUNT(DISTINCT upstream_id) FROM ContentMapping WHERE upstream_id IS NOT NULL) / (SELECT COUNT(*) FROM UpstreamTopic), 1) AS upstream_coverage_pct, " +
        "ROUND(100.0 * (SELECT COUNT(DISTINCT downstream_id) FROM ContentMapping WHERE downstream_id IS NOT NULL) / (SELECT COUNT(*) FROM DownstreamTopic), 1) AS downstream_coverage_pct",
    },
    {
      id: "by-derivation-type",
      title: "Mappings by Derivation Type",
      description: "Count of mappings per derivation type",
      category: "summary",
      sql:
        "SELECT derivation_type, COUNT(*) AS count " +
        "FROM ContentMapping GROUP BY derivation_type ORDER BY count DESC",
    },
    {
      id: "by-nav-section",
      title: "Downstream by Nav Section",
      description: "Distribution of downstream topics across navigation sections",
      category: "summary",
      sql:
        "SELECT nav_section, COUNT(*) AS count " +
        "FROM DownstreamTopic GROUP BY nav_section ORDER BY count DESC",
    },
    {
      id: "by-content-type",
      title: "Upstream by Content Type",
      description: "ASSEMBLY / CONCEPT / TASK / REFERENCE breakdown",
      category: "summary",
      sql:
        "SELECT COALESCE(content_type, '(unclassified)') AS content_type, COUNT(*) AS count " +
        "FROM UpstreamTopic GROUP BY content_type ORDER BY count DESC",
    },
    {
      id: "coverage-gaps",
      title: "Coverage Gaps",
      description: "Upstream topics with no downstream match",
      category: "gaps",
      sql:
        "SELECT u.id, u.title, u.content_type, u.source_category " +
        "FROM UpstreamTopic u LEFT JOIN ContentMapping m ON u.id = m.upstream_id " +
        "WHERE m.id IS NULL ORDER BY u.path",
    },
    {
      id: "downstream-only",
      title: "Downstream-Only Topics",
      description: "Topics that exist only in downstream, no upstream source",
      category: "gaps",
      sql:
        "SELECT d.title, d.nav_section, d.dita_type " +
        "FROM ContentMapping m JOIN DownstreamTopic d ON m.downstream_id = d.id " +
        "WHERE m.derivation_type = 'downstream_only' ORDER BY d.nav_section, d.title",
    },
    {
      id: "rewritten-restructured",
      title: "Rewritten / Restructured",
      description: "Mappings where content was significantly changed",
      category: "gaps",
      sql:
        "SELECT m.derivation_type, u.title AS upstream_title, d.title AS downstream_title, d.nav_section " +
        "FROM ContentMapping m " +
        "LEFT JOIN UpstreamTopic u ON m.upstream_id = u.id " +
        "LEFT JOIN DownstreamTopic d ON m.downstream_id = d.id " +
        "WHERE m.derivation_type IN ('rewritten', 'restructured') " +
        "ORDER BY m.derivation_type, u.title",
    },
    {
      id: "needs-work",
      title: "Upstream Needing Work",
      description: "Topics with status needs_work",
      category: "gaps",
      sql:
        "SELECT u.id, u.title, u.content_type, u.source_category " +
        "FROM UpstreamTopic u WHERE u.status = 'needs_work' ORDER BY u.path",
    },
    {
      id: "full-detail",
      title: "Full Mapping Detail",
      description: "Complete upstream-to-downstream join",
      category: "detail",
      sql:
        "SELECT m.derivation_type, u.title AS upstream_title, u.path AS upstream_path, " +
        "d.title AS downstream_title, d.nav_section, d.dita_type " +
        "FROM ContentMapping m " +
        "LEFT JOIN UpstreamTopic u ON m.upstream_id = u.id " +
        "LEFT JOIN DownstreamTopic d ON m.downstream_id = d.id " +
        "ORDER BY m.derivation_type, u.path",
    },
  ];

  var db = null;
  var currentResult = null;
  var currentTitle = "";

  function loadSqlJs() {
    return new Promise(function (resolve, reject) {
      if (window.initSqlJs) {
        resolve(window.initSqlJs);
        return;
      }
      var script = document.createElement("script");
      script.src =
        "https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.3/sql-wasm.js";
      script.onload = function () {
        resolve(window.initSqlJs);
      };
      script.onerror = function () {
        reject(new Error("Failed to load sql.js"));
      };
      document.head.appendChild(script);
    });
  }

  function initDatabase() {
    var status = document.getElementById("status-bar");
    status.textContent = "Loading sql.js engine…";

    loadSqlJs()
      .then(function (initSqlJs) {
        return initSqlJs({
          locateFile: function (file) {
            return (
              "https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.3/" + file
            );
          },
        });
      })
      .then(function (SQL) {
        status.textContent = "Fetching database…";
        var dbUrl = new URL(container.dataset.dbUrl, document.baseURI).href;
        return fetch(dbUrl).then(function (resp) {
          if (!resp.ok) throw new Error("HTTP " + resp.status);
          return resp.arrayBuffer().then(function (buf) {
            return { SQL: SQL, buf: buf };
          });
        });
      })
      .then(function (result) {
        db = new result.SQL.Database(new Uint8Array(result.buf));
        status.textContent =
          "Database loaded. Select a report or write a query.";
        enableCards();
      })
      .catch(function (err) {
        status.textContent = "Error: " + err.message;
        status.style.color = "#d32f2f";
      });
  }

  function renderReportCards() {
    var grid = document.getElementById("report-cards");
    REPORTS.forEach(function (report) {
      var card = document.createElement("div");
      card.className = "report-card";
      card.dataset.reportId = report.id;
      card.setAttribute("role", "button");
      card.setAttribute("tabindex", "0");
      card.innerHTML =
        '<div class="report-card-category">' +
        escapeHtml(report.category) +
        "</div>" +
        '<div class="report-card-title">' +
        escapeHtml(report.title) +
        "</div>" +
        '<div class="report-card-desc">' +
        escapeHtml(report.description) +
        "</div>";
      card.addEventListener("click", function () {
        runReport(report);
      });
      card.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          runReport(report);
        }
      });
      grid.appendChild(card);
    });
  }

  function enableCards() {
    var cards = document.querySelectorAll(".report-card");
    cards.forEach(function (c) {
      c.style.opacity = "1";
    });
  }

  function runReport(report) {
    var cards = document.querySelectorAll(".report-card");
    cards.forEach(function (c) {
      c.classList.toggle("active", c.dataset.reportId === report.id);
    });
    executeAndRender(report.title, report.sql);
  }

  function executeAndRender(title, sql) {
    var status = document.getElementById("status-bar");
    if (!db) {
      status.textContent = "Database not loaded yet.";
      return;
    }
    try {
      var results = db.exec(sql);
      if (results.length === 0) {
        currentResult = { columns: [], values: [] };
      } else {
        currentResult = results[0];
      }
      currentTitle = title;
      renderResults(title, currentResult);
      status.textContent = title;
    } catch (err) {
      status.textContent = "Query error: " + err.message;
      status.style.color = "#d32f2f";
      setTimeout(function () {
        status.style.color = "";
      }, 3000);
    }
  }

  function renderResults(title, result) {
    var section = document.getElementById("results-section");
    var titleEl = document.getElementById("results-title");
    var countEl = document.getElementById("results-count");
    var thead = document.getElementById("results-thead");
    var tbody = document.getElementById("results-tbody");

    titleEl.textContent = title;
    countEl.textContent =
      result.values.length === 1
        ? "1 row"
        : result.values.length + " rows";

    var headerRow = "<tr>";
    result.columns.forEach(function (col) {
      headerRow += "<th>" + escapeHtml(col) + "</th>";
    });
    headerRow += "</tr>";
    thead.innerHTML = headerRow;

    var bodyHtml = "";
    result.values.forEach(function (row) {
      bodyHtml += "<tr>";
      row.forEach(function (val) {
        bodyHtml +=
          "<td>" + escapeHtml(val === null ? "" : String(val)) + "</td>";
      });
      bodyHtml += "</tr>";
    });
    tbody.innerHTML = bodyHtml;

    section.style.display = "block";
  }

  function exportCsv() {
    if (!currentResult || currentResult.columns.length === 0) return;

    var lines = [];
    lines.push(currentResult.columns.map(csvEscape).join(","));
    currentResult.values.forEach(function (row) {
      lines.push(
        row
          .map(function (v) {
            return csvEscape(v === null ? "" : String(v));
          })
          .join(",")
      );
    });

    var blob = new Blob([lines.join("\n")], { type: "text/csv" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download =
      (currentTitle || "query").replace(/[^a-z0-9]+/gi, "-").toLowerCase() +
      ".csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  function csvEscape(val) {
    var s = String(val);
    if (s.indexOf(",") !== -1 || s.indexOf('"') !== -1 || s.indexOf("\n") !== -1) {
      return '"' + s.replace(/"/g, '""') + '"';
    }
    return s;
  }

  function escapeHtml(str) {
    var div = document.createElement("div");
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  document.addEventListener("DOMContentLoaded", function () {
    renderReportCards();
    initDatabase();

    document.getElementById("run-sql").addEventListener("click", function () {
      var sql = document.getElementById("sql-input").value.trim();
      if (sql) {
        document.querySelectorAll(".report-card").forEach(function (c) {
          c.classList.remove("active");
        });
        executeAndRender("Custom Query", sql);
      }
    });

    document.getElementById("clear-sql").addEventListener("click", function () {
      document.getElementById("sql-input").value = "";
    });

    document
      .getElementById("sql-input")
      .addEventListener("keydown", function (e) {
        if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
          e.preventDefault();
          document.getElementById("run-sql").click();
        }
      });

    document
      .getElementById("export-csv")
      .addEventListener("click", exportCsv);
  });
})();
