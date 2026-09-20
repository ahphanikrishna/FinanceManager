/* Dashboard 2x2 financial grid: grouped category/subcategory selection with
   dynamic sum recalculation and per-card monthly trend charts.
   Selection is client-side only; no page refreshes. */
(function () {
  'use strict';

  var grid = document.querySelector('.fin-grid');
  if (!grid) return;

  var dataEl = document.getElementById('fin-grid-data');
  var data = null;
  try {
    data = JSON.parse(dataEl.textContent);
  } catch (err) {
    return;
  }

  // Same palette as the top dashboard metric cards.
  var COLORS = {
    Expenditure: '#e02424',
    Income: '#10b981',
    Investment: '#3498db',
    Transfer: '#2980b9'
  };

  function formatMoney(value) {
    return '\u20b9' + Number(value || 0).toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  }

  function compactNumber(value) {
    if (Math.abs(value) >= 10000000) return (value / 10000000).toFixed(1) + 'Cr';
    if (Math.abs(value) >= 100000) return (value / 100000).toFixed(1) + 'L';
    return String(value);
  }

  function forEachIn(scope, selector, fn) {
    Array.prototype.forEach.call(scope.querySelectorAll(selector), fn);
  }

  var cards = document.querySelectorAll('.fin-card');
  Array.prototype.forEach.call(cards, function (card) {
    var type = card.getAttribute('data-fin-type');
    var totalEl = card.querySelector('[data-fin-total]');
    var countEl = card.querySelector('[data-fin-count]');
    var canvas = card.querySelector('.fin-trend');
    var itemChecks = Array.prototype.slice.call(card.querySelectorAll('.fin-item-check'));
    var subToggles = Array.prototype.slice.call(card.querySelectorAll('.fin-sub-toggle'));
    var groupToggles = Array.prototype.slice.call(card.querySelectorAll('.fin-group-toggle'));

    var cardData = (data.cards || []).find(function (entry) { return entry.type === type; });
    var allSeries = (cardData && cardData.trend && cardData.trend['All'])
      || data.labels.map(function () { return 0; });

    function recalc() {
      var sum = 0;
      var count = 0;
      itemChecks.forEach(function (check) {
        if (check.checked) {
          sum += Number(check.closest('.fin-item').getAttribute('data-amount') || 0);
          count += 1;
        }
      });
      totalEl.textContent = formatMoney(sum);
      countEl.textContent = itemChecks.length
        ? count + ' of ' + itemChecks.length + ' selected'
        : 'No items this month';

      subToggles.forEach(function (toggle) {
        syncToggle(toggle, toggle.closest('.fin-sub'));
      });
      groupToggles.forEach(function (toggle) {
        syncToggle(toggle, toggle.closest('.fin-group'));
      });
    }

    function syncToggle(toggle, scope) {
      var checks = Array.prototype.slice.call(scope.querySelectorAll('.fin-item-check'));
      var on = checks.filter(function (check) { return check.checked; }).length;
      toggle.checked = checks.length > 0 && on === checks.length;
      toggle.indeterminate = on > 0 && on < checks.length;
    }

    function setChecked(scope, selector, checked) {
      forEachIn(scope, selector, function (check) { check.checked = checked; });
    }

    if (typeof window.Chart !== 'undefined' && canvas) {
      var color = COLORS[type] || '#6366f1';
      new Chart(canvas, {
        type: 'line',
        data: {
          labels: data.labels,
          datasets: [{
            label: card.getAttribute('aria-label') || type,
            data: allSeries,
            borderColor: color,
            backgroundColor: color + '1f',
            fill: true,
            tension: 0.3,
            pointRadius: 3,
            borderWidth: 2
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: function (ctx) { return formatMoney(ctx.parsed.y); }
              }
            }
          },
          scales: {
            y: {
              beginAtZero: true,
              ticks: { callback: compactNumber }
            }
          }
        }
      });
    }

    subToggles.forEach(function (toggle) {
      toggle.addEventListener('change', function () {
        setChecked(toggle.closest('.fin-sub'), '.fin-item-check', toggle.checked);
        recalc();
      });
    });

    groupToggles.forEach(function (toggle) {
      toggle.addEventListener('change', function () {
        setChecked(toggle.closest('.fin-group'), '.fin-item-check', toggle.checked);
        recalc();
      });
    });

    forEachIn(card, '[data-fin-action]', function (button) {
      button.addEventListener('click', function () {
        var checked = button.getAttribute('data-fin-action') === 'all';
        setChecked(card, '.fin-item-check', checked);
        recalc();
      });
    });

    forEachIn(card, '.fin-collapse-toggle', function (button) {
      button.addEventListener('click', function () {
        var group = button.closest('.fin-group');
        var collapsed = group.classList.toggle('collapsed');
        button.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
        button.title = collapsed ? 'Expand category' : 'Collapse category';
      });
    });

    itemChecks.forEach(function (check) {
      check.addEventListener('change', recalc);
    });

    recalc();
  });
})();
