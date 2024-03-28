document.addEventListener('DOMContentLoaded', function() {
    // Initial setup and event listeners
    setupEventListeners();
    initDragAndDrop(); // Initialize drag-and-drop functionality
});



function setupEventListeners() {
    document.getElementById('month-select').addEventListener('change', handleMonthChange);
    document.getElementById('prev-week').addEventListener('click', () => handleWeekChange(-7));
    document.getElementById('next-week').addEventListener('click', () => handleWeekChange(7));
}

function handleMonthChange(e) {
    const month = e.target.value;
    const year = new Date().getFullYear(); // Adjust if you need to handle different years
    navigateToMonth(year, month);
}

function handleWeekChange(dayDelta) {
    let currentWeekStart = moment.tz(document.getElementById('schedule-grid').getAttribute('data-week-start'), "Europe/Berlin");
    let newWeekStart = currentWeekStart.clone().add(dayDelta, 'days');
    
    // Adjust if not Monday
    if (newWeekStart.day() !== 1) {
        newWeekStart.day(dayDelta > 0 ? 1 : -6);
    }
    
    navigateToWeek(newWeekStart.toDate());
}

function navigateToWeek(newWeekStart) {
    const weekStartStr = moment(newWeekStart).format('YYYY-MM-DD');
    updateScheduleView({ week_start: weekStartStr });
}

function navigateToMonth(year, month) {
    const firstDayOfMonth = new Date(year, month - 1, 1);
    while (firstDayOfMonth.getDay() !== 1) {
        firstDayOfMonth.setDate(firstDayOfMonth.getDate() + 1);
    }
    navigateToWeek(firstDayOfMonth);
}

function updateScheduleView(params) {
    const queryString = new URLSearchParams(params).toString();
    const url = `/schedule/?${queryString}`;

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
        const scheduleGrid = document.getElementById('schedule-grid');
        // Clear existing content from the schedule grid before setting new HTML
        while (scheduleGrid.firstChild) {
            scheduleGrid.removeChild(scheduleGrid.firstChild);
        }
        scheduleGrid.innerHTML = html;
        const weekStartStr = params.week_start;
        scheduleGrid.setAttribute('data-week-start', weekStartStr);

        // Wait for the new content to be fully loaded before reinitializing drag and drop
        setTimeout(initDragAndDrop, 0);
    })
    .catch(error => {
        console.error('Error:', error);
    });
}


// This is a placeholder function to indicate where you should define or redefine the
// drag-and-drop functionality based on your existing implementation or any adjustments you make.
function initDragAndDrop() {
    // Initialize or reinitialize drag-and-drop functionality here.
    // This should include destroying any previous Dragula instances and creating a new one.
}
