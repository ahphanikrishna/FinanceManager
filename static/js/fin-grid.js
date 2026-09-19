/* Dashboard 2x2 financial grid: category filtering, item selection with
   dynamic sum recalculation, and per-category monthly trend charts.
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

  var COLORS = {
    Expenditure: '#ef4444',
    Income: '#22c55e',
    Investment: '#3b82f6',
    Transfer: '#f59e0b'
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

  function splitKey(value) {
    if (!value) return { cat: null, sub: null };
    var idx = value.indexOf('|');
    if (idx === -1) return { cat: value, sub: null };
    return { cat: value.slice(0, idx), sub: value.slice(idx + 1) };
  }

  var cards = document.querySelectorAll('.fin-card');
  Array.prototype.forEach.call(cards, function (card) {
    var type = card.getAttribute('data-fin-type');
    var select = card.querySelector('.fin-category-select');
    var items = Array.prototype.slice.call(card.querySelectorAll('.fin-item'));
    var totalEl = card.querySelector('[data-fin-total]');
    var countEl = card.querySelector('[data-fin-count]');
    var canvas = card.querySelector('.fin-trend');
    var chart = null;

    var cardData = (data.cards || []).find(function (entry) { return entry.type === type; });
    var trend = (cardData && cardData.trend) || {};

    function visibleItems() {
      var key = splitKey(select.value);
      if (!key.cat) return items;
      return items.filter(function (li) {
        if (li.getAttribute('data-category') !== key.cat) return false;
        return key.sub === null || li.getAttribute('data-subcategory') === key.sub;
      });
    }

    function recalc() {
      var visible = visibleItems();
      var sum = 0;
      var count = 0;
      visible.forEach(function (li) {
        var check = li.querySelector('.fin-item-check');
        if (check.checked) {
          sum += Number(li.getAttribute('data-amount') || 0);
          count += 1;
        }
      });
      totalEl.textContent = formatMoney(sum);
      countEl.textContent = visible.length
        ? count + ' of ' + visible.length + ' selected'
        : 'No items for this selection';
    }

    function updateChart() {
      if (typeof window.Chart === 'undefined' || !canvas) return;
      var series = trend[select.value || 'All'] || data.labels.map(function () { return 0; });
      if (!chart) {
        var color = COLORS[type] || '#6366f1';
        chart = new Chart(canvas, {
          type: 'line',
          data: {
            labels: data.labels,
            datasets: [{
              label: card.getAttribute('aria-label') || type,
              data: series,
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
      } else {
        chart.data.datasets[0].data = series;
      }
      chart.update();
    }

    function applyFilter() {
      var visible = visibleItems();
      items.forEach(function (li) {
        li.hidden = visible.indexOf(li) === -1;
      });
      recalc();
      updateChart();
    }

    select.addEventListener('change', applyFilter);

    Array.prototype.forEach.call(card.querySelectorAll('[data-fin-action]'), function (button) {
      button.addEventListener('click', function () {
        var checked = button.getAttribute('data-fin-action') === 'all';
        visibleItems().forEach(function (li) {
          li.querySelector('.fin-item-check').checked = checked;
        });
        recalc();
      });
    });

    Array.prototype.forEach.call(card.querySelectorAll('.fin-item-check'), function (check) {
      check.addEventListener('change', recalc);
    });

    applyFilter();
  });
})();
