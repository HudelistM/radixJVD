document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('month-select').addEventListener('change', handleMonthChange);
    document.getElementById('prev-week').addEventListener('click', () => handleWeekChange(-7));
    document.getElementById('next-week').addEventListener('click', () => handleWeekChange(7));
});

function handleMonthChange(e) {
    const month = e.target.value;
    const year = new Date().getFullYear(); // Adjust if you need to handle different years
    navigateToMonth(year, month);
}

function handleWeekChange(dayDelta) {
    const currentWeekStart = new Date(document.getElementById('schedule-grid').getAttribute('data-week-start'));
    const newWeekStart = new Date(currentWeekStart);
    newWeekStart.setDate(currentWeekStart.getDate() + dayDelta);
    navigateToWeek(newWeekStart);
}

function navigateToWeek(newWeekStart) {
    const weekStartStr = newWeekStart.toISOString().split('T')[0]; // Format to 'YYYY-MM-DD'
    updateScheduleView({ week_start: weekStartStr });
}

function navigateToMonth(year, month) {
    const firstDayOfMonth = new Date(year, month - 1, 1);
    // Find the first Monday of the month or adjust according to your needs
    while (firstDayOfMonth.getDay() !== 1) {
        firstDayOfMonth.setDate(firstDayOfMonth.getDate() + 1);
    }
    navigateToWeek(firstDayOfMonth);
}

function updateScheduleView(params) {
    const queryString = new URLSearchParams(params).toString();
    const url = `/schedule/?${queryString}`;
    

    // Ensure to send the request header that indicates an AJAX request
    fetch(url, {
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => {
        if (!response.ok) throw new Error('Network response was not ok');
        return response.text();
    })
    .then(html => {
        document.getElementById('schedule-grid').innerHTML = html;
        setTimeout(initDragAndDrop, 0); // This delays the re-initialization just a bit
    })
    .catch(error => {
        console.error('Error:', error);
    });
}