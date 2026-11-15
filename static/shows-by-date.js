// Moves shows whose date has passed (Prague time) from the upcoming list to the past list,
// so the page stays correct between rebuilds. Today's show stays upcoming until the day ends.
(function () {
    var today = new Date().toLocaleDateString('sv-SE', { timeZone: 'Europe/Prague' });
    var upcoming = document.querySelector('.concert-list[data-kind="upcoming"]');
    if (!upcoming) return;
    var past = document.querySelector('.concert-list[data-kind="past"]');
    var expired = Array.prototype.filter.call(upcoming.children, function (li) {
        var d = li.getAttribute('data-date');
        return d && d < today;
    });
    if (!expired.length) return;
    // upcoming is ascending, past is newest first: inserting in order at the top of past reversed
    expired.reverse().forEach(function (li) {
        if (past) past.insertBefore(li, past.firstChild); else upcoming.removeChild(li);
    });
    if (!upcoming.children.length) {
        var section = upcoming.closest('section');
        var msg = document.createElement('p');
        msg.className = 'page-body';
        msg.textContent = 'No upcoming shows.';
        if (past) upcoming.parentNode.replaceChild(msg, upcoming);
        else if (section) section.style.display = 'none';
    }
})();
