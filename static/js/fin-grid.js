/* Dashboard tabs, 2x2 financial grid grouped selection with dynamic sum
   recalculation, and per-card monthly trend charts. All client-side; no
   page refreshes. */
(function () {
  'use strict';

  var dataEl = document.getElementById('fin-grid-data');
  if (!dataEl) return;
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

  var chartInits = [];
  var chartInstances = {};

  var cards = document.querySelectorAll('.fin-card');
  Array.prototype.forEach.call(cards, function (card) {
    var type = card.getAttribute('data-fin-type');
    var totalEl = card.querySelector('[data-fin-total]');
    var countEl = card.querySelector('[data-fin-count]');
    var canvas = document.querySelector('.fin-chart[data-fin-type="' + type + '"] .fin-trend');
    var itemChecks = Array.prototype.slice.call(card.querySelectorAll('.fin-item-check'));
    var subToggles = Array.prototype.slice.call(card.querySelectorAll('.fin-sub-toggle'));
    var groupToggles = Array.prototype.slice.call(card.querySelectorAll('.fin-group-toggle'));

    var select = document.querySelector('.fin-chart[data-fin-type="' + type + '"] .fin-chart-select');
    var cardData = (data.cards || []).find(function (entry) { return entry.type === type; });
    var allSeries = (cardData && cardData.trend && cardData.trend['All'])
      || data.labels.map(function () { return 0; });

    function seriesFor(key) {
      return (cardData && cardData.trend && cardData.trend[key]) || allSeries;
    }

    function labelFor(key) {
      if (!key || key === 'All') {
        return card.getAttribute('aria-label') || type;
      }
      if (key.indexOf('|') !== -1) {
        var parts = key.split('|');
        return parts[0] + ' \u2192 ' + parts[1];
      }
      return key;
    }

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

    chartInits.push(function () {
      if (typeof window.Chart === 'undefined' || !canvas) return;
      var color = COLORS[type] || '#6366f1';
      var key = select ? select.value : 'All';
      chartInstances[type] = new Chart(canvas, {
        type: 'line',
        data: {
          labels: data.labels,
          datasets: [{
            label: labelFor(key),
            data: seriesFor(key),
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
    });

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

    forEachIn(card, '.fin-collapse-toggle', function (button) {
      button.addEventListener('click', function () {
        var group = button.closest('.fin-group');
        var collapsed = group.classList.toggle('collapsed');
        button.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
        button.title = collapsed ? 'Expand category' : 'Collapse category';
      });
    });

    forEachIn(card, '.fin-sub-collapse', function (button) {
      button.addEventListener('click', function () {
        var sub = button.closest('.fin-sub');
        var collapsed = sub.classList.toggle('collapsed');
        button.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
        button.title = collapsed ? 'Expand subcategory' : 'Collapse subcategory';
      });
    });

    forEachIn(card, '[data-fin-action]', function (button) {
      button.addEventListener('click', function () {
        var checked = button.getAttribute('data-fin-action') === 'all';
        setChecked(card, '.fin-item-check', checked);
        recalc();
      });
    });

    itemChecks.forEach(function (check) {
      check.addEventListener('change', recalc);
    });

    if (select) {
      select.addEventListener('change', function () {
        var chart = chartInstances[type];
        if (chart) {
          chart.data.datasets[0].data = seriesFor(select.value);
          chart.data.datasets[0].label = labelFor(select.value);
          chart.update();
        }
      });
    }

    recalc();
  });

  // Charts are created lazily so the canvas has real dimensions the first
  // time the graphs tab is shown.
  var chartsReady = false;
  function initCharts() {
    if (chartsReady) return;
    chartsReady = true;
    chartInits.forEach(function (init) { init(); });
  }

  var tabButtons = Array.prototype.slice.call(document.querySelectorAll('.dash-tab'));
  if (tabButtons.length) {
    function activateTab(name) {
      tabButtons.forEach(function (btn) {
        var on = btn.getAttribute('data-dash-tab') === name;
        btn.classList.toggle('active', on);
        btn.setAttribute('aria-selected', on ? 'true' : 'false');
      });
      Array.prototype.forEach.call(document.querySelectorAll('.dash-panel'), function (panel) {
        panel.hidden = panel.getAttribute('data-dash-panel') !== name;
      });
      if (name === 'graphs') initCharts();
    }
    tabButtons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        activateTab(btn.getAttribute('data-dash-tab'));
      });
    });
    var defaultBtn = tabButtons.filter(function (btn) {
      return btn.classList.contains('active');
    })[0];
    activateTab(defaultBtn ? defaultBtn.getAttribute('data-dash-tab') : 'insights');
  } else {
    initCharts();
  }
})();
