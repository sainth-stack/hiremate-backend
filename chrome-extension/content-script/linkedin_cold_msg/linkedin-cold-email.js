// ─── LinkedIn AI Assistant Module ─────────────────────────────────────────
// Brain icon on ALL LinkedIn text inputs: messages, comments, job fields.
// Exports: window.__HM_COLD_EMAIL__ = { startColdEmailModule, stopColdEmailModule, isLinkedInMessagingPage }
// Depends on: generateColdMessage, generateComment, generateJobAnswer (cold-message-api.js)
//             getAutofillContextFromApi (autofill-context.js)

(function () {
  var ANCHOR_ATTR = "data-hm-cold-anchor";
  var HISTORY_KEY = "hm_ce_history";
  var HISTORY_MAX = 15;

  // ── Selectors ─────────────────────────────────────────────────────────────
  // Covers: messaging, InMail, overlay compose, comments, job application fields,
  // post creation. Listed from most-specific to most-generic.
  var COMPOSER_SELECTORS = [
    // Messaging
    'div.msg-form__contenteditable[contenteditable="true"]',
    'div[contenteditable="true"].msg-form__contenteditable',
    'div[role="textbox"][aria-label*="message" i]',
    'div[role="textbox"][aria-label*="Write" i]',
    'div[contenteditable="true"].msg-overlay-conversation-bubble__content-wrapper',
    // Replies to comments (more specific — must come before generic comment selectors)
    'div[role="textbox"][aria-label*="reply" i]',
    'div[role="textbox"][aria-placeholder*="reply" i]',
    '.comments-reply-texteditor div[contenteditable="true"]',
    '.comments-reply-box div[contenteditable="true"]',
    // Comments on posts
    'div[role="textbox"][aria-label*="comment" i]',
    'div[role="textbox"][aria-placeholder*="comment" i]',
    '.comments-comment-texteditor div[contenteditable="true"]',
    '.comments-comment-box--cr div[contenteditable="true"]',
    '.comments-comment-box div[contenteditable="true"]',
    // Job application forms (Easy Apply)
    '.jobs-easy-apply-content textarea',
    '.jobs-easy-apply-content div[contenteditable="true"]',
    '.application-outlet textarea',
    // Post / article creation
    '.share-creation-state div[role="textbox"]',
    '.share-box-feed-entry__trigger-container div[contenteditable="true"]',
    // Generic — catches remaining inputs not matched above
    'div[role="textbox"][contenteditable="true"]',
    'textarea',
  ];

  var _observer = null;
  var _pollTimer = null;
  var _active = false;

  // ── Lifecycle ──────────────────────────────────────────────────────────────

  function isLinkedInMessagingPage() {
    return location.hostname.includes("linkedin.com");
  }

  function startColdEmailModule() {
    if (!location.hostname.includes("linkedin.com")) return;
    if (_active) { _attachToComposers(); return; }
    _active = true;
    _startObserver();
  }

  function stopColdEmailModule() {
    _active = false;
    if (_observer) { _observer.disconnect(); _observer = null; }
    if (_pollTimer) { clearInterval(_pollTimer); _pollTimer = null; }
    document.querySelectorAll(".hm-ce-popup[data-hm-open]").forEach(function (p) { p.remove(); });
    document.querySelectorAll(".hm-ce-icon-btn[data-hm-floating]").forEach(function (i) { i.remove(); });
    document.querySelectorAll("[" + ANCHOR_ATTR + "]").forEach(function (el) { el.removeAttribute(ANCHOR_ATTR); });
  }

  function _startObserver() {
    var debounceTimer = null;
    _observer = new MutationObserver(function () {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(_attachToComposers, 200);
    });
    _observer.observe(document.body, { childList: true, subtree: true });
    _attachToComposers();
    setTimeout(_attachToComposers, 500);
    setTimeout(_attachToComposers, 1500);
    _pollTimer = setInterval(_attachToComposers, 1500);
  }

  // ── Element discovery ──────────────────────────────────────────────────────

  function _attachToComposers() {
    if (!_active) return;
    _resolveComposers().forEach(function (composer) {
      if (composer.hasAttribute(ANCHOR_ATTR)) return;
      if (!document.contains(composer)) return;
      composer.setAttribute(ANCHOR_ATTR, "true");
      var icon = _createFloatingIcon(composer);
      icon.addEventListener("click", function (e) {
        e.stopPropagation();
        _togglePopup(icon, composer);
      });
    });
  }

  // Returns true for elements that should never get the brain icon
  function _shouldSkipElement(el) {
    // Skip search boxes
    var ariaLabel = (el.getAttribute("aria-label") || "").toLowerCase();
    if (ariaLabel.includes("search")) return true;
    if (el.tagName === "INPUT" && (el.type === "search" || el.type === "email" || el.type === "tel")) return true;

    // Walk ancestors — skip nav / search containers
    var anc = el.parentElement;
    for (var i = 0; i < 10; i++) {
      if (!anc) break;
      var cls = (anc.className || "").toString();
      var role = anc.getAttribute ? (anc.getAttribute("role") || "") : "";
      if (cls.includes("search-global-typeahead") || cls.includes("global-nav__search") ||
          role === "search" || role === "navigation") return true;
      anc = anc.parentElement;
    }
    return false;
  }

  function _resolveComposers() {
    var seen = new Set();
    var results = [];
    for (var i = 0; i < COMPOSER_SELECTORS.length; i++) {
      var found;
      try { found = Array.from(document.querySelectorAll(COMPOSER_SELECTORS[i])); }
      catch (_) { found = []; }
      for (var j = 0; j < found.length; j++) {
        var el = found[j];
        if (!seen.has(el) && !_shouldSkipElement(el)) {
          seen.add(el);
          results.push(el);
        }
      }
    }
    return results;
  }

  // ── Context detection ──────────────────────────────────────────────────────
  // Returns: "message" | "comment" | "job" | "general"

  function _detectFieldContext(composer) {
    var ariaLabel = (
      composer.getAttribute("aria-label") ||
      composer.getAttribute("aria-placeholder") ||
      composer.getAttribute("placeholder") || ""
    ).toLowerCase();
    if (ariaLabel.includes("reply")) return "reply";
    if (ariaLabel.includes("comment") || ariaLabel.includes("add a comment")) return "comment";
    if (ariaLabel.includes("message") || ariaLabel.includes("write a message")) return "message";

    // Walk ancestors
    var el = composer.parentElement;
    for (var i = 0; i < 15; i++) {
      if (!el) break;
      var cls = (el.className || "").toString().toLowerCase();
      if (cls.includes("msg-form") || cls.includes("msg-overlay") || cls.includes("msg-compose") ||
          cls.includes("messaging-thread") || el.id && el.id.includes("msg-")) return "message";
      if (cls.includes("comments-reply") || cls.includes("reply-texteditor") ||
          cls.includes("replies-list") || cls.includes("create-reply") ||
          cls.includes("reply-box")) return "reply";
      if (cls.includes("comments-comment") || cls.includes("comment-texteditor") ||
          cls.includes("comment-box") || cls.includes("comments-text-editor")) return "comment";
      if (cls.includes("jobs-easy-apply") || cls.includes("application-outlet") ||
          cls.includes("easy-apply") || cls.includes("job-application")) return "job";
      if (cls.includes("share-creation-state") || cls.includes("share-box-feed-entry")) return "general";
      el = el.parentElement;
    }

    if (location.pathname.startsWith("/messaging")) return "message";
    if (location.pathname.includes("/jobs/")) return "job";
    return "general";
  }

  // ── Context scrapers ───────────────────────────────────────────────────────

  function _scrapePostContext(composer) {
    // ── Class-name-free approach ───────────────────────────────────────────
    // LinkedIn changes class names constantly. Instead of relying on them,
    // we use pure DOM structure: the post text is always a PRECEDING SIBLING
    // (or sibling subtree) of the branch that contains the comment box.
    //
    // Walk up the DOM keeping track of which child is "our branch".
    // At each level, collect text from all sibling children that come BEFORE
    // our branch and are NOT comment-related. When we accumulate >100 chars
    // of preceding text, we've found the post body level.
    //
    // The LONGEST preceding text block = post content.
    // The FIRST preceding text block   = author / header.

    var prevEl = composer;
    var el = composer.parentElement;

    for (var depth = 0; depth < 60; depth++) {
      if (!el || el === document.body) break;

      var children = Array.from(el.children);
      var branchIdx = children.indexOf(prevEl);

      if (branchIdx > 0) {
        // Collect text from all siblings that come BEFORE our branch
        var textBlocks = [];
        for (var j = 0; j < branchIdx; j++) {
          var sib = children[j];
          // Skip elements that are part of the comment UI
          var sibCls = (sib.className || "").toString().toLowerCase();
          if (sibCls.includes("comment") || sibCls.includes("reply")) continue;
          var t = (sib.textContent || "").trim();
          if (t.length > 20) textBlocks.push(t);
        }

        var combined = textBlocks.join("\n");
        if (combined.length > 100) {
          // The longest block is the post body (not author name / button labels)
          var postContent = textBlocks.reduce(function (best, b) {
            return b.length > best.length ? b : best;
          }, "");
          // First short block is usually the author name
          var postAuthor = "";
          for (var k = 0; k < textBlocks.length; k++) {
            var lines = textBlocks[k].split(/\n|\r/).map(function (l) { return l.trim(); }).filter(Boolean);
            if (lines[0] && lines[0].length > 2 && lines[0].length < 80) {
              postAuthor = lines[0];
              break;
            }
          }
          console.log("[HM] postContext depth=" + depth + " author=" + postAuthor.slice(0, 40) + " content=" + postContent.slice(0, 60));
          return {
            postContent: postContent.slice(0, 1200),
            postAuthor: postAuthor || null,
          };
        }
      }

      prevEl = el;
      el = el.parentElement;
    }

    console.log("[HM] postContext: NOT FOUND after 60 levels");
    return { postContent: null, postAuthor: null };
  }

  function _scrapeJobContext(composer) {
    // Field label
    var fieldLabel = "";
    var id = composer.getAttribute("id");
    if (id) {
      var lbl = document.querySelector('label[for="' + id + '"]');
      if (lbl) fieldLabel = lbl.textContent.trim();
    }
    if (!fieldLabel) {
      fieldLabel =
        composer.getAttribute("aria-label") ||
        composer.getAttribute("placeholder") ||
        composer.getAttribute("name") || "";
    }
    if (!fieldLabel) {
      var anc = composer.parentElement;
      for (var i = 0; i < 6; i++) {
        if (!anc) break;
        var lel = anc.querySelector("label, h3, h4, legend, span.jobs-easy-apply-form-section__grouping");
        if (lel && !lel.contains(composer)) { fieldLabel = lel.textContent.trim(); break; }
        anc = anc.parentElement;
      }
    }

    // Job title + company
    var jobTitle = "";
    var company = "";
    var titleEl =
      document.querySelector(".jobs-unified-top-card__job-title") ||
      document.querySelector(".job-details-jobs-unified-top-card__job-title") ||
      document.querySelector("h1.t-24.t-bold");
    if (titleEl) jobTitle = _firstLine(titleEl.textContent);

    var companyEl =
      document.querySelector(".jobs-unified-top-card__company-name") ||
      document.querySelector(".job-details-jobs-unified-top-card__company-name") ||
      document.querySelector(".jobs-unified-top-card__subtitle-primary-grouping");
    if (companyEl) company = _firstLine(companyEl.textContent);

    return {
      fieldLabel: fieldLabel.slice(0, 200),
      jobTitle: jobTitle.slice(0, 100),
      company: company.slice(0, 100),
    };
  }

  // ── Floating brain icon ────────────────────────────────────────────────────

  function _createFloatingIcon(composer) {
    var icon = document.createElement("button");
    icon.className = "hm-ce-icon-btn";
    icon.setAttribute("data-hm-floating", "true");
    icon.title = "AI assist (HireMate)";
    icon.setAttribute("aria-label", "HireMate AI assist");
    icon.innerHTML =
      '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">' +
      '<path d="M13 3C9.23 3 6.19 5.95 6 9.67l-1.99 2.98A1 1 0 005 14h1v3c0 1.1.9 2 2 2h1v3h7v-4.08c2.34-.96 4-3.26 4-5.92 0-3.87-3.13-7-7-7zm1 14.93V19h-4v-3H8v-4H6.74l1.48-2.23C8.64 7.55 10.68 6 13 6c2.76 0 5 2.24 5 5 0 2.37-1.65 4.38-4 4.93zM13 10h-2v3h2v-3zm0-3h-2v2h2V7z"/>' +
      "</svg>";

    function reposition() {
      if (!_active || !document.contains(composer)) { icon.remove(); return; }
      var rect = composer.getBoundingClientRect();
      if (rect.width === 0 && rect.height === 0) { icon.style.display = "none"; return; }
      icon.style.display = "flex";
      icon.style.position = "fixed";
      icon.style.left = (rect.left + 6) + "px";
      // Comments and replies: icon sits at the bottom-left inside the textarea.
      // Messages and all others: icon sits just above the textarea (original behaviour).
      var fieldCtx = _detectFieldContext(composer);
      if (fieldCtx === "comment" || fieldCtx === "reply") {
        icon.style.top = (rect.bottom - 38) + "px";
      } else {
        icon.style.top = (rect.top - 18) + "px";
      }
      icon.style.zIndex = "2147483645";
    }

    document.body.appendChild(icon);
    reposition();

    var _scroll = function () { reposition(); };
    var _resize = function () { reposition(); };
    window.addEventListener("scroll", _scroll, true);
    window.addEventListener("resize", _resize, true);

    var _cleanup = setInterval(function () {
      if (!_active || !document.contains(composer)) {
        icon.remove();
        clearInterval(_cleanup);
        window.removeEventListener("scroll", _scroll, true);
        window.removeEventListener("resize", _resize, true);
        if (document.contains(composer)) composer.removeAttribute(ANCHOR_ATTR);
      } else {
        reposition();
      }
    }, 300);

    return icon;
  }

  // ── Popup routing ──────────────────────────────────────────────────────────

  function _togglePopup(icon, composer) {
    var existing = document.querySelector(".hm-ce-popup[data-hm-open]");
    if (existing) { existing.remove(); return; }
    var ctx = _detectFieldContext(composer);
    if (ctx === "reply") {
      _openReplyPopup(icon, composer);
    } else if (ctx === "comment") {
      _openCommentPopup(icon, composer);
    } else if (ctx === "job") {
      _openJobPopup(icon, composer);
    } else {
      _openMessagePopup(icon, composer); // "message" and "general"
    }
  }

  function _positionPopup(popup, icon) {
    var rect = icon.getBoundingClientRect();
    popup.style.position = "fixed";
    popup.style.zIndex = "2147483646";
    popup.style.width = "340px";
    var popupHeight = 420;
    if (rect.top - popupHeight < 8) {
      popup.style.top = (rect.bottom + 8) + "px";
      popup.style.bottom = "auto";
    } else {
      popup.style.bottom = (window.innerHeight - rect.top + 8) + "px";
      popup.style.top = "auto";
    }
    var left = rect.left;
    if (left + 340 > window.innerWidth - 8) left = window.innerWidth - 348;
    if (left < 8) left = 8;
    popup.style.left = left + "px";
    popup.style.right = "auto";
  }

  // Shared: create popup shell, wire outside-click close, return { popup, outsideClick }
  function _buildPopupShell(icon, title) {
    var popup = document.createElement("div");
    popup.className = "hm-ce-popup";
    popup.setAttribute("data-hm-open", "true");

    function outsideClick(e) {
      if (!popup.contains(e.target) && e.target !== icon) {
        popup.remove();
        document.removeEventListener("click", outsideClick, true);
      }
    }
    setTimeout(function () {
      document.addEventListener("click", outsideClick, true);
    }, 0);

    popup._closePopup = function () {
      popup.remove();
      document.removeEventListener("click", outsideClick, true);
    };

    popup.innerHTML =
      '<div class="hm-ce-header">' +
        '<div class="hm-ce-header-left">' +
          '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M13 3C9.23 3 6.19 5.95 6 9.67l-1.99 2.98A1 1 0 005 14h1v3c0 1.1.9 2 2 2h1v3h7v-4.08c2.34-.96 4-3.26 4-5.92 0-3.87-3.13-7-7-7zm1 14.93V19h-4v-3H8v-4H6.74l1.48-2.23C8.64 7.55 10.68 6 13 6c2.76 0 5 2.24 5 5 0 2.37-1.65 4.38-4 4.93zM13 10h-2v3h2v-3zm0-3h-2v2h2V7z"/></svg>' +
          "<span>" + _esc(title) + "</span>" +
        "</div>" +
        '<button class="hm-ce-close-x" data-hm-close title="Close">&#x2715;</button>' +
      "</div>";

    document.body.appendChild(popup);
    popup.querySelector("[data-hm-close]").addEventListener("click", popup._closePopup);
    return popup;
  }

  // Shared: wire preset chips to fill the intent textarea
  function _wirePresets(popup) {
    popup.querySelectorAll(".hm-ce-preset").forEach(function (chip) {
      chip.addEventListener("click", function () {
        var intentEl = popup.querySelector("#hm-ce-intent");
        if (intentEl) { intentEl.value = chip.dataset.text || ""; intentEl.focus(); }
      });
    });
  }

  // Shared: show generate + error footer HTML
  function _footerHtml(label) {
    return (
      '<div class="hm-ce-footer">' +
        '<button class="hm-ce-generate-btn" id="hm-ce-generate">' +
          '<span id="hm-ce-generate-label">' + (label || "Generate") + "</span>" +
          '<span class="hm-ce-spinner" id="hm-ce-spinner" style="display:none"></span>' +
        "</button>" +
        '<div class="hm-ce-error" id="hm-ce-error" style="display:none"></div>' +
      "</div>"
    );
  }

  // Shared: spin/unspin button
  function _startSpin(popup) {
    var btn = popup.querySelector("#hm-ce-generate");
    var lbl = popup.querySelector("#hm-ce-generate-label");
    var sp = popup.querySelector("#hm-ce-spinner");
    btn.disabled = true;
    if (lbl) lbl.textContent = "Generating\u2026";
    if (sp) sp.style.display = "";
    popup.querySelector("#hm-ce-error").style.display = "none";
    return function stopSpin() {
      btn.disabled = false;
      if (lbl) lbl.textContent = "Generate";
      if (sp) sp.style.display = "none";
    };
  }

  // ── Message popup ──────────────────────────────────────────────────────────

  var MSG_PRESETS = [
    { label: "Ask for referral", text: "Ask for a referral to an open role at their company" },
    { label: "Job openings?",   text: "Ask if there are any open positions at their company or team" },
    { label: "Intro call",      text: "Request a short 15-minute intro call to learn more about their work" },
    { label: "General intro",   text: "Introduce myself and express interest in connecting professionally" },
    { label: "Career advice",   text: "Ask for career advice based on their experience and background" },
    { label: "Shared connection", text: "Reach out based on a shared connection, school, or company" },
  ];

  function _openMessagePopup(icon, composer) {
    var scraped = _scrapeRecipientInfo();
    _loadHistory().then(function (history) {
      var popup = _buildPopupShell(icon, "Draft Message");

      var presetHtml = MSG_PRESETS.map(function (p) {
        return '<button class="hm-ce-preset" data-text="' + _esc(p.text) + '">' + _esc(p.label) + "</button>";
      }).join("");

      var recentHtml = "";
      if (history.length > 0) {
        recentHtml =
          '<div class="hm-ce-section"><div class="hm-ce-section-label">Recent</div>' +
          '<div class="hm-ce-preset-chips">' +
          history.slice(0, 3).map(function (h) {
            return '<button class="hm-ce-preset hm-ce-recent" data-text="' + _esc(h.prompt) + '">' + _esc(_truncate(h.prompt, 26)) + "</button>";
          }).join("") + "</div></div>";
      }

      popup.innerHTML += (
        '<div class="hm-ce-section" style="padding-top:14px;">' +
          '<div class="hm-ce-section-label">Quick intents</div>' +
          '<div class="hm-ce-preset-chips">' + presetHtml + "</div>" +
        "</div>" +
        recentHtml +
        '<div class="hm-ce-intent-wrap">' +
          '<textarea class="hm-ce-intent-input" id="hm-ce-intent" rows="3" placeholder="Describe what you want to say\u2026"></textarea>' +
        "</div>" +
        _footerHtml("Generate")
      );

      _wirePresets(popup);
      _positionPopup(popup, icon);

      popup.querySelector("#hm-ce-generate").addEventListener("click", function () {
        var intent = (popup.querySelector("#hm-ce-intent").value || "").trim();
        if (!intent) { _showError(popup.querySelector("#hm-ce-error"), "Please describe your intent."); return; }
        var stopSpin = _startSpin(popup);
        var threadCtx = _scrapeThreadContext();
        var ctxParts = [];
        if (scraped.name) ctxParts.push("Recipient: " + scraped.name);
        if (scraped.headline) ctxParts.push("Headline: " + scraped.headline);
        else if (scraped.company) ctxParts.push("Company: " + scraped.company);
        if (ctxParts.length) threadCtx = ctxParts.join("\n") + (threadCtx ? "\n" + threadCtx : "");

        _getSenderSummary().then(function (senderSummary) {
          return generateColdMessage({
            user_intent: intent,
            recipient_name: scraped.name || null,
            company: scraped.company || null,
            tone: "professional",
            thread_context: threadCtx ? threadCtx.slice(0, 1000) : null,
            sender_profile_summary: senderSummary || null,
          });
        }).then(function (result) {
          _saveHistory({ prompt: intent, createdAt: Date.now() });
          _showResult(popup, composer, result.message);
        }).catch(function (err) {
          _showError(popup.querySelector("#hm-ce-error"), (err && err.message) || "Generation failed. Try again.");
          stopSpin();
        });
      });
    });
  }

  // ── Comment popup ──────────────────────────────────────────────────────────

  var COMMENT_PRESETS = [
    { label: "Add perspective",     text: "Add my professional perspective on this topic" },
    { label: "Ask follow-up",       text: "Ask a thoughtful follow-up question about the main point" },
    { label: "Share experience",    text: "Share a related personal or professional experience" },
    { label: "Agree & expand",      text: "Agree with the key idea and expand on it with more context" },
    { label: "Disagree politely",   text: "Respectfully share a different viewpoint with reasoning" },
    { label: "Tag for visibility",  text: "Engage to boost visibility and add value to the thread" },
  ];

  function _openCommentPopup(icon, composer) {
    var ctx = _scrapePostContext(composer);
    var popup = _buildPopupShell(icon, "Write Comment");

    var presetHtml = COMMENT_PRESETS.map(function (p) {
      return '<button class="hm-ce-preset" data-text="' + _esc(p.text) + '">' + _esc(p.label) + "</button>";
    }).join("");

    var postPreview = "";
    if (ctx.postContent) {
      postPreview =
        '<div class="hm-ce-section" style="padding-top:12px;">' +
          '<div class="hm-ce-section-label">Post context' + (ctx.postAuthor ? " · " + _esc(ctx.postAuthor) : "") + "</div>" +
          '<div class="hm-ce-post-preview">' + _esc(_truncate(ctx.postContent, 120)) + "</div>" +
        "</div>";
    }

    popup.innerHTML += (
      postPreview +
      '<div class="hm-ce-section" style="padding-top:10px;">' +
        '<div class="hm-ce-section-label">Comment angle</div>' +
        '<div class="hm-ce-preset-chips">' + presetHtml + "</div>" +
      "</div>" +
      '<div class="hm-ce-intent-wrap">' +
        '<textarea class="hm-ce-intent-input" id="hm-ce-intent" rows="2" placeholder="Optional: what\u2019s your specific angle?"></textarea>' +
      "</div>" +
      _footerHtml("Generate Comment")
    );

    _wirePresets(popup);
    _positionPopup(popup, icon);

    popup.querySelector("#hm-ce-generate").addEventListener("click", function () {
      var intent = (popup.querySelector("#hm-ce-intent").value || "").trim();
      var stopSpin = _startSpin(popup);

      _getSenderSummary().then(function (senderSummary) {
        return generateComment({
          post_content: ctx.postContent || null,
          post_author: ctx.postAuthor || null,
          user_intent: intent || null,
          sender_profile_summary: senderSummary || null,
          tone: "professional",
        });
      }).then(function (result) {
        _showResult(popup, composer, result.message);
      }).catch(function (err) {
        _showError(popup.querySelector("#hm-ce-error"), (err && err.message) || "Generation failed. Try again.");
        stopSpin();
      });
    });
  }

  // ── Reply popup ───────────────────────────────────────────────────────────

  var REPLY_PRESETS = [
    { label: "Agree & add",       text: "Agree with this comment and add a supporting point" },
    { label: "Ask follow-up",     text: "Ask a thoughtful follow-up question about what they said" },
    { label: "Share experience",  text: "Share a related personal experience in response" },
    { label: "Politely disagree", text: "Respectfully share a different perspective with reasoning" },
    { label: "Thank & expand",    text: "Thank them and expand on the idea they raised" },
    { label: "Add resource",      text: "Suggest a useful resource or article related to their point" },
  ];

  function _scrapeParentComment(composer) {
    // LinkedIn reply DOM: the reply box sits INSIDE the parent comment-item.
    // Strategy: walk up until we find the comment-item container, then extract
    // text from it while EXCLUDING our own reply-box subtree.

    // Helper: check if a node is an ancestor-or-self of the composer
    function _isOwnSubtree(node) {
      var c = composer;
      while (c) { if (c === node) return true; c = c.parentElement; }
      return false;
    }

    // Helper: strip noisy short tokens (Like, Reply, timestamps, emoji counts)
    function _cleanText(t) {
      return t
        .replace(/\b(Like|Reply|See\s+\d+\s+replies?|Edited|Report\s+this\s+comment)\b/gi, "")
        .replace(/^\s*[\d·•|]+\s*/gm, "")
        .replace(/\s{2,}/g, " ")
        .trim();
    }

    var el = composer.parentElement;
    for (var i = 0; i < 25; i++) {
      if (!el || el === document.body) break;
      var cls = (el.className || "").toString().toLowerCase();

      // Found the enclosing comment item — extract text from it
      if (cls.includes("comment-item") || cls.includes("comments-comment")) {
        // Collect all text-bearing leaf nodes that are NOT inside our reply subtree
        var bestText = "";

        // Priority 1: spans/paragraphs with dir="ltr" (LinkedIn's comment text spans)
        var spans = Array.from(el.querySelectorAll('span[dir="ltr"], p[dir="ltr"]'));
        for (var k = 0; k < spans.length; k++) {
          if (_isOwnSubtree(spans[k])) continue;
          var t = _cleanText(spans[k].textContent || "");
          if (t.length > bestText.length) bestText = t;
        }
        if (bestText.length > 20) return bestText.slice(0, 300);

        // Priority 2: any class containing "comment-text", "main-content", "body"
        var textEls = Array.from(el.querySelectorAll('[class*="comment-text"],[class*="main-content"],[class*="comment__content"],[class*="comment-body"]'));
        for (var k = 0; k < textEls.length; k++) {
          if (_isOwnSubtree(textEls[k])) continue;
          var t = _cleanText(textEls[k].textContent || "");
          if (t.length > bestText.length) bestText = t;
        }
        if (bestText.length > 20) return bestText.slice(0, 300);

        // Priority 3: walk direct children, skip social-bar / reply-box subtrees,
        // take the child with the most text
        var children = Array.from(el.children);
        for (var k = 0; k < children.length; k++) {
          var child = children[k];
          if (_isOwnSubtree(child)) continue;
          var childCls = (child.className || "").toString().toLowerCase();
          if (childCls.includes("social-bar") || childCls.includes("reply-box") ||
              childCls.includes("reply-list") || childCls.includes("toolbar")) continue;
          var t = _cleanText(child.textContent || "");
          if (t.length > bestText.length) bestText = t;
        }
        if (bestText.length > 20) return bestText.slice(0, 300);
      }

      el = el.parentElement;
    }

    // Last resort: check aria-label / placeholder on the composer for the author name
    var label = composer.getAttribute("aria-label") || composer.getAttribute("aria-placeholder") || "";
    var m = label.match(/reply(?:\s+to)?\s+(.+?)(?:'s|$)/i);
    return m ? "Replying to " + m[1].trim() : "";
  }

  function _openReplyPopup(icon, composer) {
    var parentComment = _scrapeParentComment(composer);
    var postCtx = _scrapePostContext(composer);
    var popup = _buildPopupShell(icon, "Write Reply");

    var presetHtml = REPLY_PRESETS.map(function (p) {
      return '<button class="hm-ce-preset" data-text="' + _esc(p.text) + '">' + _esc(p.label) + "</button>";
    }).join("");

    var commentPreview = "";
    if (parentComment) {
      commentPreview =
        '<div class="hm-ce-section" style="padding-top:12px;">' +
          '<div class="hm-ce-section-label">Replying to</div>' +
          '<div class="hm-ce-post-preview">' + _esc(_truncate(parentComment, 140)) + "</div>" +
        "</div>";
    }

    popup.innerHTML += (
      commentPreview +
      '<div class="hm-ce-section" style="padding-top:10px;">' +
        '<div class="hm-ce-section-label">Reply angle</div>' +
        '<div class="hm-ce-preset-chips">' + presetHtml + "</div>" +
      "</div>" +
      '<div class="hm-ce-intent-wrap">' +
        '<textarea class="hm-ce-intent-input" id="hm-ce-intent" rows="2" placeholder="Optional: your specific angle for the reply\u2026"></textarea>' +
      "</div>" +
      _footerHtml("Generate Reply")
    );

    _wirePresets(popup);
    _positionPopup(popup, icon);

    popup.querySelector("#hm-ce-generate").addEventListener("click", function () {
      var intent = (popup.querySelector("#hm-ce-intent").value || "").trim();
      var stopSpin = _startSpin(popup);

      _getSenderSummary().then(function (senderSummary) {
        return generateComment({
          post_content: parentComment || postCtx.postContent || null,
          post_author: postCtx.postAuthor || null,
          user_intent: intent || null,
          sender_profile_summary: senderSummary || null,
          tone: "professional",
          is_reply: true,
        });
      }).then(function (result) {
        _showResult(popup, composer, result.message);
      }).catch(function (err) {
        _showError(popup.querySelector("#hm-ce-error"), (err && err.message) || "Generation failed. Try again.");
        stopSpin();
      });
    });
  }

  // ── Job answer popup ───────────────────────────────────────────────────────

  var JOB_PRESETS = [
    { label: "Why this role",   text: "Explain why I am the right fit for this specific role" },
    { label: "Cover letter",    text: "Write a concise cover letter highlighting my most relevant experience" },
    { label: "Why this company", text: "Explain why I want to work at this specific company" },
    { label: "Key strengths",   text: "Highlight my top 3 strengths relevant to this job" },
    { label: "Career goals",    text: "Describe how this role fits into my career goals" },
    { label: "Biggest achievement", text: "Describe my biggest professional achievement relevant to this role" },
  ];

  function _openJobPopup(icon, composer) {
    var ctx = _scrapeJobContext(composer);
    var popup = _buildPopupShell(icon, "Fill Application Field");

    var presetHtml = JOB_PRESETS.map(function (p) {
      return '<button class="hm-ce-preset" data-text="' + _esc(p.text) + '">' + _esc(p.label) + "</button>";
    }).join("");

    var fieldInfo = "";
    if (ctx.fieldLabel || ctx.jobTitle) {
      var infoText = [];
      if (ctx.fieldLabel) infoText.push("Field: " + _esc(ctx.fieldLabel));
      if (ctx.jobTitle)   infoText.push("Role: " + _esc(ctx.jobTitle));
      if (ctx.company)    infoText.push("Company: " + _esc(ctx.company));
      fieldInfo =
        '<div class="hm-ce-section" style="padding-top:12px;">' +
          '<div class="hm-ce-section-label">Detected context</div>' +
          '<div class="hm-ce-post-preview">' + infoText.join(" · ") + "</div>" +
        "</div>";
    }

    popup.innerHTML += (
      fieldInfo +
      '<div class="hm-ce-section" style="padding-top:10px;">' +
        '<div class="hm-ce-section-label">What to write</div>' +
        '<div class="hm-ce-preset-chips">' + presetHtml + "</div>" +
      "</div>" +
      '<div class="hm-ce-intent-wrap">' +
        '<textarea class="hm-ce-intent-input" id="hm-ce-intent" rows="2" placeholder="Any extra guidance? (optional)"></textarea>' +
      "</div>" +
      _footerHtml("Generate Answer")
    );

    _wirePresets(popup);
    _positionPopup(popup, icon);

    popup.querySelector("#hm-ce-generate").addEventListener("click", function () {
      var intent = (popup.querySelector("#hm-ce-intent").value || "").trim();
      var stopSpin = _startSpin(popup);

      _getSenderSummary().then(function (senderSummary) {
        return generateJobAnswer({
          field_label: ctx.fieldLabel || null,
          job_title: ctx.jobTitle || null,
          company: ctx.company || null,
          user_intent: intent || null,
          sender_profile_summary: senderSummary || null,
          tone: "professional",
        });
      }).then(function (result) {
        _showResult(popup, composer, result.message);
      }).catch(function (err) {
        _showError(popup.querySelector("#hm-ce-error"), (err && err.message) || "Generation failed. Try again.");
        stopSpin();
      });
    });
  }

  // ── Result screen (shared by all contexts) ─────────────────────────────────

  function _showResult(popup, composer, message) {
    var title = popup.querySelector(".hm-ce-header-left span");
    var titleText = title ? title.textContent : "Generated text";
    popup._closePopup && popup._closePopup; // keep reference alive
    popup.innerHTML =
      '<div class="hm-ce-header">' +
        '<div class="hm-ce-header-left">' +
          '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M13 3C9.23 3 6.19 5.95 6 9.67l-1.99 2.98A1 1 0 005 14h1v3c0 1.1.9 2 2 2h1v3h7v-4.08c2.34-.96 4-3.26 4-5.92 0-3.87-3.13-7-7-7zm1 14.93V19h-4v-3H8v-4H6.74l1.48-2.23C8.64 7.55 10.68 6 13 6c2.76 0 5 2.24 5 5 0 2.37-1.65 4.38-4 4.93zM13 10h-2v3h2v-3zm0-3h-2v2h2V7z"/></svg>' +
          "<span>" + _esc(titleText) + "</span>" +
        "</div>" +
        '<button class="hm-ce-close-x" id="hm-ce-close-result" title="Close">&#x2715;</button>' +
      "</div>" +
      '<div class="hm-ce-result-wrap">' +
        '<div class="hm-ce-result-label">Generated text — review before using</div>' +
        '<textarea class="hm-ce-result-textarea" id="hm-ce-result-text">' + _esc(message) + "</textarea>" +
      "</div>" +
      '<div class="hm-ce-footer">' +
        '<button class="hm-ce-use-btn" id="hm-ce-use">Use Text</button>' +
        '<button class="hm-ce-back-link" id="hm-ce-back">&#8592; Back</button>' +
      "</div>";

    popup.querySelector("#hm-ce-use").addEventListener("click", function () {
      _fillComposer(composer, popup.querySelector("#hm-ce-result-text").value);
      popup.remove();
    });
    popup.querySelector("#hm-ce-back").addEventListener("click", function () { popup.remove(); });
    popup.querySelector("#hm-ce-close-result").addEventListener("click", function () { popup.remove(); });
  }

  // ── Scrapers ───────────────────────────────────────────────────────────────

  function _scrapeRecipientInfo() {
    var name = "";
    var company = "";
    var headline = "";

    var nameSelectors = [
      ".msg-overlay-bubble-header__details h2",
      ".msg-overlay-bubble-header .t-bold",
      ".msg-thread__link-to-profile",
      ".msg-overlay-bubble-header__title",
      ".msg-conversation-listitem--active .msg-conversation-listitem__participant-names",
      "h1.text-heading-xlarge",
      "h1.inline.t-24",
    ];
    for (var i = 0; i < nameSelectors.length; i++) {
      var el = document.querySelector(nameSelectors[i]);
      if (el) { var c = _firstLine(el.textContent); if (c && c.length > 1) { name = c; break; } }
    }

    var companySelectors = [
      ".msg-overlay-bubble-header__details .t-12",
      ".msg-entity-lockup__subtitle",
      ".text-body-medium.break-words",
      "h2.top-card-layout__headline",
      ".pv-text-details__left-panel .text-body-medium",
    ];
    for (var j = 0; j < companySelectors.length; j++) {
      var cel = document.querySelector(companySelectors[j]);
      if (cel) { var t = _firstLine(cel.textContent); if (t && t.length > 1) { headline = t.slice(0, 200); break; } }
    }
    if (headline) {
      var m = headline.match(/[@|at|@]\s*([A-Z][^|•·,]+)/i);
      company = m ? m[1].trim().slice(0, 120) : headline.slice(0, 120);
    }
    return { name: name, company: company, headline: headline };
  }

  function _scrapeThreadContext() {
    var parts = [];
    var headlineEl =
      document.querySelector(".text-body-medium.break-words") ||
      document.querySelector("h2.top-card-layout__headline") ||
      document.querySelector(".pv-text-details__left-panel .text-body-medium");
    if (headlineEl) { var hl = (headlineEl.textContent || "").trim(); if (hl) parts.push("Profile: " + hl.slice(0, 300)); }
    var lastMsg =
      document.querySelector(".msg-s-message-list__event:last-child .msg-s-event-listitem__body") ||
      document.querySelector(".msg-overlay-conversation-bubble__content .msg-s-event-listitem__body:last-child");
    if (lastMsg) { var mt = (lastMsg.textContent || "").trim(); if (mt) parts.push("Last message: " + mt.slice(0, 200)); }
    return parts.length ? parts.join("\n").slice(0, 1000) : null;
  }

  // ── Sender profile summary ─────────────────────────────────────────────────

  function _getSenderSummary() {
    return new Promise(function (resolve) {
      try {
        getAutofillContextFromApi().then(function (ctx) {
          var p = ctx.profile || {};
          var parts = [];
          var name = (p.name || ((p.firstName || "") + " " + (p.lastName || "")).trim()).trim();
          if (name) parts.push("Name: " + name);
          var headline = p.professionalHeadline || p.title || "";
          if (headline) parts.push("Headline: " + headline);
          var exps = Array.isArray(p.experiences) ? p.experiences : [];
          if (exps.length > 0) {
            var latest = exps[0];
            var roleStr = [latest.jobTitle, latest.companyName].filter(Boolean).join(" at ");
            if (roleStr) parts.push("Current role: " + roleStr);
          }
          var totalYears = 0;
          exps.forEach(function (exp) {
            var s = exp.startDate ? parseInt(exp.startDate) : null;
            var e = exp.endDate ? parseInt(exp.endDate) : new Date().getFullYear();
            if (s && e >= s) totalYears += (e - s);
          });
          if (totalYears > 0) parts.push("Years of experience: " + totalYears + "+");
          var skills = (p.tech_skills_list || []).slice(0, 8).join(", ") ||
                       (p.skills || "").split(",").slice(0, 8).join(", ").trim();
          if (skills) parts.push("Skills: " + skills);
          if (p.professionalSummary) parts.push("Summary: " + p.professionalSummary.slice(0, 250));
          resolve(parts.length ? parts.join("\n") : null);
        }).catch(function () { resolve(null); });
      } catch (_) { resolve(null); }
    });
  }

  // ── Fill target element ────────────────────────────────────────────────────

  function _fillComposer(composer, text) {
    composer.focus();

    // Native textarea / input — use value setter + React-compatible events
    if (composer.tagName === "TEXTAREA" || composer.tagName === "INPUT") {
      var proto = composer.tagName === "TEXTAREA"
        ? window.HTMLTextAreaElement.prototype
        : window.HTMLInputElement.prototype;
      var nativeSetter = Object.getOwnPropertyDescriptor(proto, "value");
      if (nativeSetter && nativeSetter.set) {
        nativeSetter.set.call(composer, text);
      } else {
        composer.value = text;
      }
      composer.dispatchEvent(new Event("input", { bubbles: true }));
      composer.dispatchEvent(new Event("change", { bubbles: true }));
      return;
    }

    // contenteditable div — clear via Selection API then insert DOM nodes
    var sel = window.getSelection();
    try {
      var clearRange = document.createRange();
      clearRange.selectNodeContents(composer);
      sel.removeAllRanges();
      sel.addRange(clearRange);
      sel.deleteFromDocument();
    } catch (_) {
      composer.innerHTML = "";
    }

    var frag = document.createDocumentFragment();
    text.split(/\n{2,}/).forEach(function (para) {
      var p = document.createElement("p");
      para.split("\n").forEach(function (line, i) {
        if (i > 0) p.appendChild(document.createElement("br"));
        p.appendChild(document.createTextNode(line));
      });
      frag.appendChild(p);
    });
    composer.appendChild(frag);
    try {
      composer.dispatchEvent(new InputEvent("input", { bubbles: true, cancelable: true, inputType: "insertText" }));
    } catch (_) {
      composer.dispatchEvent(new Event("input", { bubbles: true }));
    }

    try {
      var range = document.createRange();
      var sel = window.getSelection();
      range.selectNodeContents(composer);
      range.collapse(false);
      sel.removeAllRanges();
      sel.addRange(range);
    } catch (_) {}
  }

  // ── History ────────────────────────────────────────────────────────────────

  function _loadHistory() {
    return new Promise(function (resolve) {
      chrome.storage.local.get([HISTORY_KEY], function (result) { resolve(result[HISTORY_KEY] || []); });
    });
  }

  function _saveHistory(entry) {
    return _loadHistory().then(function (history) {
      var updated = [entry].concat(history).slice(0, HISTORY_MAX);
      return new Promise(function (resolve) {
        chrome.storage.local.set({ [HISTORY_KEY]: updated }, resolve);
      });
    });
  }

  // ── Utilities ──────────────────────────────────────────────────────────────

  function _firstLine(raw) {
    if (!raw) return "";
    var lines = (raw || "").split(/\n|\r/);
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i].trim();
      if (line.length > 0) return line.slice(0, 100);
    }
    return "";
  }

  function _truncate(str, max) {
    return str && str.length > max ? str.slice(0, max) + "\u2026" : (str || "");
  }

  function _esc(str) {
    return (str || "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function _showError(el, msg) {
    el.textContent = msg;
    el.style.display = "block";
  }

  // ── Export ─────────────────────────────────────────────────────────────────

  window.__HM_COLD_EMAIL__ = {
    startColdEmailModule: startColdEmailModule,
    stopColdEmailModule: stopColdEmailModule,
    isLinkedInMessagingPage: isLinkedInMessagingPage,
  };
})();
