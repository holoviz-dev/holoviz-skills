/**
 * Adds a "Copy Markdown" button to skill pages.
 *
 * build_stubs.py injects a hidden <div data-skill-source="..."> element into
 * every generated skill page.  This script reads that element, constructs the
 * raw GitHub URL, fetches the original SKILL.md, strips YAML front matter,
 * and copies the clean Markdown to the clipboard.
 */
document.addEventListener("DOMContentLoaded", function () {
  var meta = document.querySelector("[data-skill-source]");
  if (!meta) return;                         // not a skill page

  var sourcePath = meta.getAttribute("data-skill-source");
  var repo = "holoviz-dev/holoviz-skills";
  var branch = "main";
  var rawUrl =
    "https://raw.githubusercontent.com/" +
    repo + "/" + branch + "/" + sourcePath;

  // ---- SVG icons ----
  var COPY_ICON =
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">' +
    '<path d="M19 21H8V7h11m0-2H8a2 2 0 0 0-2 2v14a2 2 0 0 0 2' +
    " 2h11a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2m-3-4H4a2 2 0 0 0-2" +
    ' 2v14h2V3h12V1Z"/></svg>';

  var CHECK_ICON =
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">' +
    '<path d="M21 7 9 19l-5.5-5.5 1.41-1.41L9 16.17 19.59 5.59 21 7Z"/>' +
    "</svg>";

  // ---- Build the button ----
  var btn = document.createElement("a");
  btn.className = "md-content__button md-icon";
  btn.href = "#";
  btn.setAttribute("aria-label", "Copy page as Markdown");

  btn.innerHTML = COPY_ICON;
  btn.title = "Copy page as Markdown";

  // ---- Insert alongside the existing action buttons ----
  // MkDocs Material renders action buttons (edit, view source) as
  // float:right <a> elements before the <h1> inside .md-content__inner.
  // Insert our button right before the first existing action button so
  // it joins the same float row without overlapping.
  var toolbar = document.querySelector(".md-content__inner");
  if (toolbar) {
    var firstBtn = toolbar.querySelector("a.md-content__button");
    if (firstBtn) {
      toolbar.insertBefore(btn, firstBtn);
    } else {
      var h1 = toolbar.querySelector("h1");
      if (h1) toolbar.insertBefore(btn, h1);
      else toolbar.prepend(btn);
    }
  }

  // ---- Feedback helpers ----
  var feedbackTimer = null;

  function showCopied() {
    // Swap icon to checkmark and tint green
    var svgEl = btn.querySelector("svg");
    if (svgEl) svgEl.remove();
    btn.insertAdjacentHTML("beforeend", CHECK_ICON);
    btn.style.color = "#4caf50";
    btn.title = "Copied!";

    clearTimeout(feedbackTimer);
    feedbackTimer = setTimeout(resetButton, 2000);
  }

  function resetButton() {
    var svgEl = btn.querySelector("svg");
    if (svgEl) svgEl.remove();
    btn.insertAdjacentHTML("beforeend", COPY_ICON);
    btn.style.color = "";
    btn.title = "Copy page as Markdown";
  }

  // ---- Click handler ----
  btn.addEventListener("click", function (e) {
    e.preventDefault();

    fetch(rawUrl)
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.text();
      })
      .then(function (text) {
        // Strip YAML front matter (--- ... ---) from the start of the file.
        var cleaned = text.replace(/^---\s*\n[\s\S]*?\n---\s*\n/, "");

        // Normalise line endings to \n (GitHub may serve \r\n on Windows).
        cleaned = cleaned.replace(/\r\n/g, "\n").trimStart();

        return navigator.clipboard.writeText(cleaned);
      })
      .then(showCopied)
      .catch(function (err) {
        console.error("Copy Markdown failed:", err);
        // Fallback: open raw file in new tab
        window.open(rawUrl, "_blank");
      });
  });
});
