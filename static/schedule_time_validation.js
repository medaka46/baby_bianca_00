// Warn when a task's start time is later than its end time, before submit.
//
// Only guards submit buttons marked data-validate-times="1" (ordinary tasks).
// Rule: invalid only when start is strictly AFTER end; equal times are allowed
// (preserves the 00:00-00:00 "no specific time" convention). Fails OPEN — if a
// value can't be read it allows the submit, so a JS hiccup never blocks a save.
(function (global) {
  function toMinutes(hourStr, minStr) {
    var h = parseInt(hourStr, 10);
    var m = parseInt(minStr, 10);
    if (isNaN(h) || isNaN(m)) return null;
    return h * 60 + m;
  }

  function startIsAfterEnd(startMin, endMin) {
    if (startMin === null || endMin === null) return false; // fail open
    return startMin > endMin;
  }

  function readMinutes(form, hourName, minName) {
    var h = form.elements[hourName];
    var m = form.elements[minName];
    if (!h || !m) return null;
    return toMinutes(h.value, m.value);
  }

  function toggleWarning(form, show) {
    var w = form.querySelector('.time-order-warning');
    if (w) w.style.display = show ? 'inline' : 'none';
  }

  if (typeof document !== 'undefined') {
    document.addEventListener('submit', function (event) {
      var btn = event.submitter;
      if (!btn || btn.getAttribute('data-validate-times') !== '1') return;
      var form = event.target;
      var startMin = readMinutes(form, 'start_time_hour', 'start_time_minute');
      var endMin = readMinutes(form, 'end_time_hour', 'end_time_minute');
      if (startIsAfterEnd(startMin, endMin)) {
        event.preventDefault();
        toggleWarning(form, true);
      } else {
        toggleWarning(form, false);
      }
    }, true);
  }

  // Exported for node-based unit checks; harmless in the browser.
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { toMinutes: toMinutes, startIsAfterEnd: startIsAfterEnd };
  }
})(typeof window !== 'undefined' ? window : this);
