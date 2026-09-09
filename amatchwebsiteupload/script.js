// A Match — mobile nav toggle + scroll-reveal, no dependencies.
(function () {
  var header = document.querySelector('.site-header');
  if (header) {
    var setHeaderScroll = function () {
      header.classList.toggle('scrolled', window.scrollY > 8);
    };
    setHeaderScroll();
    window.addEventListener('scroll', setHeaderScroll, { passive: true });
  }

  var toggle = document.querySelector('.nav-toggle');
  if (toggle && header) {
    toggle.addEventListener('click', function () {
      var isOpen = header.classList.toggle('nav-open');
      toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    });
    header.querySelectorAll('.nav-links a').forEach(function (link) {
      link.addEventListener('click', function () {
        header.classList.remove('nav-open');
        toggle.setAttribute('aria-expanded', 'false');
      });
    });
  }

  var prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var revealEls = document.querySelectorAll('.reveal');
  if (prefersReduced || !('IntersectionObserver' in window)) {
    revealEls.forEach(function (el) { el.classList.add('is-visible'); });
  } else {
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.15, rootMargin: '0px 0px -40px 0px' });
    revealEls.forEach(function (el) { observer.observe(el); });

    // Safety net: some browsers throttle IntersectionObserver on a
    // backgrounded/hidden document, which would otherwise leave content
    // stuck at opacity 0. Force everything visible after a short delay.
    setTimeout(function () {
      revealEls.forEach(function (el) { el.classList.add('is-visible'); });
      observer.disconnect();
    }, 2500);
  }

  document.querySelectorAll('.faq-list, .faq2-list').forEach(function (list) {
    var items = list.querySelectorAll('details');
    items.forEach(function (item) {
      item.addEventListener('toggle', function () {
        if (item.open) {
          items.forEach(function (other) {
            if (other !== item) other.open = false;
          });
        }
      });
    });
  });

  var msgForm = document.querySelector('.js-msg-form');
  if (msgForm) {
    msgForm.addEventListener('submit', function (e) {
      e.preventDefault();
      var data = new FormData(msgForm);
      var subject = msgForm.getAttribute('data-mail-subject') || 'Anfrage';
      var body = (msgForm.getAttribute('data-mail-body') || '').replace(/\{(\w+)\}/g, function (m, key) {
        return (data.get(key) || '').toString().trim() || '-';
      });
      window.location.href = 'mailto:contact@amatch.ch?subject=' + encodeURIComponent(subject) + '&body=' + encodeURIComponent(body);
    });
  }

  var newsletterForm = document.querySelector('.js-newsletter-form');
  if (newsletterForm) {
    newsletterForm.addEventListener('submit', function (e) {
      e.preventDefault();
      var email = (newsletterForm.querySelector('input[type="email"]').value || '').trim();
      var subject = newsletterForm.getAttribute('data-mail-subject') || 'Newsletter';
      var body = (newsletterForm.getAttribute('data-mail-body') || '').replace('{email}', email);
      window.location.href = 'mailto:contact@amatch.ch?subject=' + encodeURIComponent(subject) + '&body=' + encodeURIComponent(body);
    });
  }

  // ── Stellenanzeigen-Check: live automated audit (job-ad content, not SEO) ─
  var checkForm = document.querySelector('.js-website-check-form');
  if (checkForm) {
    var langPrefix = (document.documentElement.lang || 'de').slice(0, 2);
    var isLocal = location.hostname === 'localhost' || location.hostname === '127.0.0.1';
    var DEFAULT_CHECK_API = isLocal ? 'http://localhost:8913' : 'https://amatch-checker.onrender.com';
    var CHECK_API = (window.AMATCH_CHECK_API || DEFAULT_CHECK_API) + '/api/check';
    var SEND_REPORT_API = (window.AMATCH_CHECK_API || DEFAULT_CHECK_API) + '/api/send-report';
    var T = {
      de: {
        analyzing: 'Analysiere …',
        resultKicker: 'Ihr Ergebnis', overall: 'Gesamtscore',
        passedOf: function (p, t) { return p + ' von ' + t + ' Punkten erfüllt'; },
        findingsTitle: 'Erste Ansatzpunkte',
        allGood: 'Starke Anzeige, alle Punkte erfüllt!',
        errorGeneric: 'Der Check ist gerade nicht erreichbar. Bitte später erneut versuchen.',
        ctaTitle: 'Kostenloses Erstgespräch',
        ctaText: 'Besprechen Sie die Ergebnisse direkt mit mir – 20 Minuten, unverbindlich.',
        ctaBtn: 'Termin buchen',
        emailTitle: 'Ergebnis per E-Mail erhalten',
        emailText: 'Tragen Sie Ihre E-Mail ein und wir schicken Ihnen eine Kopie des Ergebnisses inklusive Grafik.',
        emailPh: 'ihre@email.ch', emailBtn: 'Ergebnis per E-Mail senden', emailSending: 'Wird gesendet …',
        emailSuccess: 'Gesendet! Bitte prüfen Sie Ihr Postfach.',
      },
      fr: {
        analyzing: 'Analyse en cours …',
        resultKicker: 'Votre résultat', overall: 'Score global',
        passedOf: function (p, t) { return p + ' sur ' + t + ' points atteints'; },
        findingsTitle: 'Premières pistes',
        allGood: 'Annonce solide, tous les points sont remplis !',
        errorGeneric: "Le check n'est pas disponible pour le moment. Merci de réessayer plus tard.",
        ctaTitle: 'Entretien initial gratuit',
        ctaText: 'Discutons des résultats ensemble – 20 minutes, sans engagement.',
        ctaBtn: 'Prendre rendez-vous',
        emailTitle: 'Recevoir le résultat par e-mail',
        emailText: 'Indiquez votre e-mail et nous vous envoyons une copie du résultat, graphique incluse.',
        emailPh: 'votre@email.ch', emailBtn: 'Envoyer le résultat par e-mail', emailSending: 'Envoi en cours …',
        emailSuccess: 'Envoyé ! Merci de vérifier votre boîte de réception.',
      },
      en: {
        analyzing: 'Analyzing …',
        resultKicker: 'Your result', overall: 'Overall score',
        passedOf: function (p, t) { return p + ' of ' + t + ' points met'; },
        findingsTitle: 'First pointers',
        allGood: 'Strong job ad, every point is covered!',
        errorGeneric: 'The check is currently unreachable. Please try again later.',
        ctaTitle: 'Free initial consultation',
        ctaText: "Let's talk through the results together – 20 minutes, no obligation.",
        ctaBtn: 'Book a call',
        emailTitle: 'Get the result by email',
        emailText: "Enter your email and we'll send you a copy of the result, chart included.",
        emailPh: 'you@email.ch', emailBtn: 'Send result by email', emailSending: 'Sending …',
        emailSuccess: 'Sent! Please check your inbox.',
      },
    };
    var strings = T[langPrefix] || T.de;
    var resultsEl = document.getElementById('checkResults');

    var esc = function (s) {
      var d = document.createElement('div');
      d.textContent = s == null ? '' : String(s);
      return d.innerHTML;
    };

    var renderError = function (msg) {
      if (!resultsEl) return;
      resultsEl.hidden = false;
      resultsEl.innerHTML = '<div class="container" style="padding:40px 0 0;"><div class="check-error">' + esc(msg) + '</div></div>';
      resultsEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
    };

    var renderResults = function (data) {
      if (!resultsEl) return;
      var cats = data.categories || {};
      var catCards = Object.keys(cats).map(function (k) {
        var c = cats[k];
        return '<div class="report-cat-card"><div class="report-card-label">' + esc(k) + '</div>' +
          '<span class="num">' + c.score + '<span>/100</span></span>' +
          '<div class="report-bar"><div class="report-bar-fill" style="width:' + c.score + '%"></div></div>' +
          '<div class="report-card-sub">' + esc(strings.passedOf(c.passed, c.total)) + '</div></div>';
      }).join('');

      var weak = (data.checks || []).filter(function (c) { return c.status !== 'pass'; })
        .sort(function (a, b) { return (a.status === 'fail' ? 0 : 1) - (b.status === 'fail' ? 0 : 1); })
        .slice(0, 4);

      var findingsHtml = weak.length
        ? '<div class="report-findings">' + weak.map(function (c) {
            var iconClass = c.status === 'fail' ? 'is-fail' : 'is-partial';
            var icon = c.status === 'fail' ? '!' : '~';
            return '<div class="report-finding"><span class="report-finding-icon ' + iconClass + '">' + icon + '</span>' +
              '<div><div class="report-finding-title">' + esc(c.name) + '</div><div class="report-finding-text">' + esc(c.finding) + '</div></div></div>';
          }).join('') + '</div>'
        : '<p class="report-all-good">' + esc(strings.allGood) + '</p>';

      var bookingLink = document.querySelector('.nav-actions a.btn-primary');
      var bookingUrl = bookingLink ? bookingLink.href : window.location.origin + '/';
      var ctaBoxHtml =
        '<div class="report-cta-box">' +
        '<h3>' + esc(strings.ctaTitle) + '</h3>' +
        '<p>' + esc(strings.ctaText) + '</p>' +
        '<a href="' + esc(bookingUrl) + '" class="btn btn-primary">' + esc(strings.ctaBtn) + '<span class="btn-arrow">&nbsp;→</span></a>' +
        '</div>';

      var emailBoxHtml =
        '<div class="report-email-box">' +
        '<h3>' + esc(strings.emailTitle) + '</h3>' +
        '<p>' + esc(strings.emailText) + '</p>' +
        '<form class="report-email-form">' +
        '<input type="email" name="reportEmail" placeholder="' + esc(strings.emailPh) + '" required>' +
        '<button type="submit" class="btn btn-secondary">' + esc(strings.emailBtn) + '</button>' +
        '</form></div>';

      resultsEl.innerHTML =
        '<div class="container" style="padding:40px 0 0;">' +
        '<div class="section-head reveal is-visible" style="text-align:center;margin-left:auto;margin-right:auto;"><span class="kicker">' + esc(strings.resultKicker) + '</span><h2>' + esc(data.url) + '</h2></div>' +
        '<div class="report-grid">' +
        '<div class="report-score-card"><div class="report-card-label">' + esc(strings.overall) + '</div>' +
        '<span class="num">' + data.overall + '<span>/100</span></span>' +
        '<div class="report-bar"><div class="report-bar-fill" style="width:' + data.overall + '%"></div></div>' +
        '<div class="report-card-sub">' + esc(strings.passedOf(data.total_passed, data.total_checks)) + '</div></div>' +
        catCards +
        '</div>' +
        '<h3 style="text-align:center;margin-top:32px;font-size:18px;">' + esc(strings.findingsTitle) + '</h3>' +
        findingsHtml +
        ctaBoxHtml +
        emailBoxHtml +
        '</div>';
      resultsEl.hidden = false;
      resultsEl.scrollIntoView({ behavior: 'smooth', block: 'start' });

      var emailForm = resultsEl.querySelector('.report-email-form');
      if (emailForm) {
        emailForm.addEventListener('submit', function (e) {
          e.preventDefault();
          var emailInput = emailForm.querySelector('input[type="email"]');
          var toEmail = (emailInput.value || '').trim();
          if (!toEmail) return;
          var sendBtn = emailForm.querySelector('button[type="submit"]');
          var originalBtnText = sendBtn.textContent;
          sendBtn.disabled = true;
          emailInput.disabled = true;
          sendBtn.textContent = strings.emailSending;
          fetch(SEND_REPORT_API, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: toEmail, url: data.url, lang: langPrefix }),
          })
            .then(function (r) { return r.json().then(function (body) { return { ok: r.ok, body: body }; }); })
            .then(function (res) {
              if (!res.ok || res.body.error) {
                sendBtn.disabled = false; emailInput.disabled = false;
                sendBtn.textContent = originalBtnText;
                emailForm.insertAdjacentHTML('beforeend',
                  '<p class="report-email-note is-error">' + esc(res.body.error || strings.errorGeneric) + '</p>');
                return;
              }
              emailForm.innerHTML = '<p class="report-email-note is-success">' + esc(strings.emailSuccess) + '</p>';
            })
            .catch(function () {
              sendBtn.disabled = false; emailInput.disabled = false;
              sendBtn.textContent = originalBtnText;
              emailForm.insertAdjacentHTML('beforeend',
                '<p class="report-email-note is-error">' + esc(strings.errorGeneric) + '</p>');
            });
        });
      }
    };

    checkForm.addEventListener('submit', function (e) {
      e.preventDefault();
      var urlInput = checkForm.querySelector('[name="url"]');
      var url = (urlInput.value || '').trim();
      if (!url) return;
      var btn = checkForm.querySelector('button[type="submit"]');
      var original = btn.innerHTML;
      btn.disabled = true;
      btn.textContent = strings.analyzing;
      fetch(CHECK_API + '?url=' + encodeURIComponent(url) + '&lang=' + langPrefix)
        .then(function (r) { return r.json().then(function (data) { return { ok: r.ok, data: data }; }); })
        .then(function (res) {
          btn.disabled = false; btn.innerHTML = original;
          if (!res.ok || res.data.error) {
            renderError(res.data.error || strings.errorGeneric);
            return;
          }
          renderResults(res.data);
        })
        .catch(function () {
          btn.disabled = false; btn.innerHTML = original;
          renderError(strings.errorGeneric);
        });
    });
  }
})();
