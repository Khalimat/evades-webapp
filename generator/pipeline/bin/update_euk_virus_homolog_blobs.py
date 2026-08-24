#!/usr/bin/env python3

import os
import sqlite3
import argparse

# Foldseek's own self-contained HTML report (`easy-search
# --format-mode 4`) renders its "Results" table with plain, static
# markup and no sort/filter/search - its own bundled JS (a small
# framework of its own, not jQuery) populates <tbody id="tableBody">
# at load time, and reuses ONE shared row (class="alignment foldseek",
# no id) to show whichever result's alignment/3D-viewer is currently
# toggled open - relocated and refilled via an unguarded
# `document.querySelector(".alignment.foldseek").replaceChildren(...)`
# in the click handler (confirmed live - no id, no null-check), and
# apparently also located relative to whichever row is "currently
# open" via DOM adjacency, not just the class selector (confirmed live
# too: even just relocating - never deleting - that shared row out of
# tbody so DataTables could init in-place made every OTHER row's
# Toggle throw the same null error, unless the pre-expanded row was
# toggled first). Their internal wiring is undocumented/minified and
# clearly depends on fragile position assumptions we can't safely
# replicate - so this patch never moves, removes, hides, or otherwise
# touches a single node inside Foldseek's own table. That ruled out
# both wrapping it in-place with DataTables (it owns and keeps
# managing that DOM subtree - isDataTable() reports true, but no
# .dataTables_wrapper ever appears) and stripping the offending
# oversized row out of it (breaks Toggle page-wide, not just for that
# row).
#
# What's left, and what's actually implemented below: read plain TEXT
# out of each genuine result row (Foldseek's own DOM is never
# modified) into a brand-new, independent table, and let DataTables
# sort/filter/search *that*. To avoid duplicating the whole results
# list on the page (a sortable copy on top of a second, static,
# unfilterable copy below - worse than the original complaint), the
# untouched original table stays hidden by default; clicking a target
# name in the sortable index reveals it and jumps straight to that
# row, where "Toggle" and everything else works exactly as Foldseek
# built it, completely unmodified.
_SORTABLE_TABLE_PATCH = """
<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.10.25/css/jquery.dataTables.min.css">
<script src="https://ajax.googleapis.com/ajax/libs/jquery/3.7.1/jquery.min.js"></script>
<script src="https://cdn.datatables.net/1.10.25/js/jquery.dataTables.min.js"></script>
<script>
(function () {
    function initSortableTable() {
        var tbody = document.getElementById("tableBody");
        var origTable = tbody ? tbody.closest("table") : null;
        if (!origTable) return;  // not a Foldseek report with this structure - no-op
        if (!tbody.children.length) {
            // Foldseek's own script populates this table asynchronously -
            // keep polling until it has, then take over.
            setTimeout(initSortableTable, 250);
            return;
        }
        if (document.getElementById("sortable-results-table")) return;  // already done

        var headRow = origTable.querySelector("thead tr");
        var headers = headRow
            ? Array.prototype.map.call(headRow.children, function (th) { return th.textContent.trim(); })
            : [];

        // Foldseek auto-expands the top hit's alignment on load via an
        // extra sibling <tr> with no header-column match (2 <td>s:
        // alignment text + TM-score) - it has no result-row anchor, so
        // filtering on that anchor's presence both identifies genuine
        // result rows and skips it, without ever touching it.
        var rows = Array.prototype.filter.call(tbody.children, function (tr) {
            return !!tr.querySelector("a[name^='aln']");
        }).map(function (tr) {
            var cells = Array.prototype.map.call(tr.children, function (td, ci) {
                return ci < headers.length ? td.textContent.trim() : null;
            }).filter(function (v) { return v !== null; });
            var anchor = tr.querySelector("a[name^='aln']").getAttribute("name");
            return { cells: cells, anchor: anchor };
        });
        if (!rows.length) return;  // detail row(s) only, or unrecognized structure - no-op

        var caption = document.createElement("p");
        caption.style.fontSize = "0.9em";
        caption.textContent = "Sortable, searchable index - click a target name to view its full alignment.";

        var newTable = document.createElement("table");
        newTable.id = "sortable-results-table";

        var newThead = document.createElement("thead");
        var newHeadRow = document.createElement("tr");
        headers.forEach(function (h) {
            var th = document.createElement("th");
            th.textContent = h;
            newHeadRow.appendChild(th);
        });
        newThead.appendChild(newHeadRow);
        newTable.appendChild(newThead);

        var newBody = document.createElement("tbody");
        rows.forEach(function (row) {
            var tr = document.createElement("tr");
            row.cells.forEach(function (text, ci) {
                var td = document.createElement("td");
                if (ci === 0) {
                    var a = document.createElement("a");
                    a.href = "#" + row.anchor;
                    a.textContent = text;
                    a.addEventListener("click", function () {
                        origTable.style.display = "";  // reveal on demand - browser then jumps to #anchor natively
                    });
                    td.appendChild(a);
                } else {
                    td.textContent = text;
                }
                tr.appendChild(td);
            });
            newBody.appendChild(tr);
        });
        newTable.appendChild(newBody);

        try {
            origTable.style.display = "none";
            origTable.parentNode.insertBefore(caption, origTable);
            origTable.parentNode.insertBefore(newTable, origTable);
            $(newTable).DataTable({
                pageLength: 25,
                order: []
            });
        } catch (e) {
            // Fall back to Foldseek's original, fully working table.
            origTable.style.display = "";
            caption.remove();
            newTable.remove();
        }
    }
    initSortableTable();
})();
</script>
""".encode("ascii")


def make_table_sortable(html: bytes) -> bytes:
    """Append the DataTables patch just before </body> (or at the end,
    for reports - like Foldseek's - that omit a closing </body>/</html>
    and rely on the browser's implicit tag insertion)."""
    if b"tableBody" not in html:
        return html  # not a report with the expected results table - leave untouched
    if b"</body>" in html:
        return html.replace(b"</body>", _SORTABLE_TABLE_PATCH + b"</body>", 1)
    return html + _SORTABLE_TABLE_PATCH


def update_euk_virus_homolog_blobs(db_path, homologs_folder):
    # Connect to the SQLite database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Retrieve all rows from the Protein table
    cursor.execute("SELECT id, euk_virus_homologs_filename FROM Protein")
    rows = cursor.fetchall()

    # Iterate over each row
    for row in rows:
        protein_id, euk_virus_homologs_filename = row

        if euk_virus_homologs_filename:
            # Construct the full path to the .html file. The metadata
            # references "<id>_model.html" but the homolog folder as
            # produced upstream just has "<id>.html" — normalize.
            actual_filename = euk_virus_homologs_filename.replace("_model.html", ".html")
            homolog_file_path = os.path.join(homologs_folder, actual_filename)

            # Check if the .pdb file exists
            if os.path.exists(homolog_file_path):
                # Read the contents of the .pdb file
                with open(homolog_file_path, 'rb') as file:
                    euk_virus_homologs_blob = make_table_sortable(file.read())

                # Update the euk_virus_homologs_blob column
                cursor.execute("UPDATE Protein SET euk_virus_homologs_blob = ? WHERE id = ?", (euk_virus_homologs_blob, protein_id))
            else:
                print(f"Warning: .html file not found for protein {protein_id}: {euk_virus_homologs_filename}")

    # Commit the changes and close the connection
    conn.commit()
    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update the euk_virus_homologs_blob column in the Protein table.")
    parser.add_argument("--db", required=True, help="Path to the SQLite database file.")
    parser.add_argument("--homologs", required=True, help="Path to the folder containing the HTML pages with euk virus homologs.")

    args = parser.parse_args()

    update_euk_virus_homolog_blobs(args.db, args.homologs)
