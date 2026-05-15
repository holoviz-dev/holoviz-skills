/**
 * Adds a "Download ZIP" button to skill pages and the home page.
 *
 * Skill pages: build_stubs.py injects a hidden <div data-skill-source="...">
 * element.  This script reads that element, resolves the correct zip from
 * assets/, and injects a download button.
 *
 * Home page: docs/index.md contains a hidden <div data-all-skills-zip> marker.
 * This script detects it and injects a button that downloads holoviz-skills.zip.
 *
 * Zip path resolution (mirrors build_plugin.py build_zips layout):
 *   category/skills/<sub>/SKILL.md  →  assets/<category>/<sub>.zip
 *   category/SKILL.md               →  assets/<category>/<category>.zip
 *   (home page marker)              →  assets/holoviz-skills.zip
 */
document.addEventListener("DOMContentLoaded", function () {
  var repo = "holoviz-dev/holoviz-skills";
  var branch = "main";
  var base = "https://raw.githubusercontent.com/" + repo + "/" + branch + "/";

  var zipUrl, zipName;

  var allMeta = document.querySelector("[data-all-skills-zip]");
  var skillMeta = document.querySelector("[data-skill-source]");

  if (allMeta) {
    // Home page — download the full collection.
    zipName = "holoviz-skills.zip";
    zipUrl = base + "assets/" + zipName;
  } else if (skillMeta) {
    // Skill page — resolve the per-skill or per-category zip.
    // Reference pages (e.g. iterating-on-panel-apps.md) are skipped —
    // they live inside a sub-skill but don't have their own zip.
    // sourcePath examples:
    //   "developing-with-holoviz/skills/hvplot/SKILL.md"
    //       → assets/developing-with-holoviz/hvplot.zip
    //   "developing-with-holoviz/SKILL.md"
    //       → assets/developing-with-holoviz/developing-with-holoviz.zip
    var sourcePath = skillMeta.getAttribute("data-skill-source");
    if (!sourcePath.endsWith("SKILL.md")) return; // reference page — no zip
    var parts = sourcePath.split("/");
    var category = parts[0];
    if (parts.length >= 4 && parts[1] === "skills") {
      zipName = parts[2] + ".zip";
    } else {
      zipName = category + ".zip";
    }
    zipUrl = base + "assets/" + category + "/" + zipName;
  } else {
    return; // neither marker present — do nothing
  }

  // ---- SVG icons ----
  var DOWNLOAD_ICON =
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">' +
    '<path d="M5 20h14v-2H5m14-9h-4V3H9v6H5l7 7 7-7Z"/></svg>';

  var CHECK_ICON =
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">' +
    '<path d="M21 7 9 19l-5.5-5.5 1.41-1.41L9 16.17 19.59 5.59 21 7Z"/>' +
    "</svg>";

  // ---- Build the button ----
  var btn = document.createElement("a");
  btn.className = "md-content__button md-icon";
  btn.href = zipUrl;
  btn.download = zipName;
  btn.setAttribute("aria-label", "Download as ZIP");
  btn.title = "Download as ZIP";
  btn.innerHTML = DOWNLOAD_ICON;

  // ---- Insert alongside the existing action buttons ----
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

  // ---- Feedback: flash checkmark on click ----
  var feedbackTimer = null;

  function showDownloaded() {
    var svgEl = btn.querySelector("svg");
    if (svgEl) svgEl.remove();
    btn.insertAdjacentHTML("beforeend", CHECK_ICON);
    btn.style.color = "#4caf50";
    btn.title = "Downloading…";
    clearTimeout(feedbackTimer);
    feedbackTimer = setTimeout(resetButton, 2000);
  }

  function resetButton() {
    var svgEl = btn.querySelector("svg");
    if (svgEl) svgEl.remove();
    btn.insertAdjacentHTML("beforeend", DOWNLOAD_ICON);
    btn.style.color = "";
    btn.title = "Download as ZIP";
  }

  btn.addEventListener("click", showDownloaded);
});
