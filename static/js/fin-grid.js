/* Dashboard 2x2 financial grid: item selection with dynamic sum
   recalculation and per-card monthly trend charts.
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

  var cards = document.querySelectorAll('.fin-card');
  Array.prototype.forEach.call(cards, function (card) {
    var type = card.getAttribute('data-fin-type');
    var items = Array.prototype.slice.call(card.querySelectorAll('.fin-item'));
    var totalEl = card.querySelector('[data-fin-total]');
    var countEl = card.querySelector('[data-fin-count]');
    var canvas = card.querySelector('.fin-trend');

    var cardData = (data.cards || []).find(function (entry) { return entry.type === type; });
    var allSeries = (cardData && cardData.trend && cardData.trend['All'])
      || data.labels.map(function () { return 0; });

    function recalc() {
      var sum = 0;
      var count = 0;
      items.forEach(function (li) {
        var check = li.querySelector('.fin-item-check');
        if (check.checked) {
          sum += Number(li.getAttribute('data-amount') || 0);
          count += 1;
        }
      });
      totalEl.textContent = formatMoney(sum);
      countEl.textContent = items.length
        ? count + ' of ' + items.length + ' selected'
        : 'No items this month';
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

    Array.prototype.forEach.call(card.querySelectorAll('[data-fin-action]'), function (button) {
      button.addEventListener('click', function () {
        var checked = button.getAttribute('data-fin-action') === 'all';
        items.forEach(function (li) {
          li.querySelector('.fin-item-check').checked = checked;
        });
        recalc();
      });
    });

    Array.prototype.forEach.call(card.querySelectorAll('.fin-item-check'), function (check) {
      check.addEventListener('change', recalc);
    });

    recalc();
  });
})();
