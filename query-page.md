# Query Provenance Data

Explore the content provenance database interactively. The database runs entirely in your browser via [sql.js](https://sql.js.org/) — no server needed.

## Reports

<div id="query-app" data-db-url="../assets/provenance.db">
<div id="status-bar">Loading database…</div>
<div id="report-cards"></div>
<details id="custom-sql-section">
<summary>Custom SQL</summary>
<textarea id="sql-input" rows="6" spellcheck="false" placeholder="SELECT m.derivation_type, u.title AS upstream, d.title AS downstream&#10;FROM ContentMapping m&#10;LEFT JOIN UpstreamTopic u ON m.upstream_id = u.id&#10;LEFT JOIN DownstreamTopic d ON m.downstream_id = d.id"></textarea>
<div id="sql-controls">
<button id="run-sql">Run Query</button>
<button id="clear-sql">Clear</button>
<span id="sql-hint">Ctrl+Enter to run</span>
</div>
</details>
<div id="results-section" style="display:none;">
<div id="results-header">
<span id="results-title"></span>
<span id="results-count"></span>
<button id="export-csv" title="Download as CSV">Export CSV</button>
</div>
<div id="results-table-wrapper">
<table id="results-table">
<thead id="results-thead"></thead>
<tbody id="results-tbody"></tbody>
</table>
</div>
</div>
</div>
