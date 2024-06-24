let drake = null;
document.addEventListener('DOMContentLoaded', function() {
    console.log(document.getElementById('employees-list'));
    console.log(document.querySelectorAll('.dropzone'));
    initDragAndDrop();
});

function initDragAndDrop() {
    if (drake) {
        console.log('Destroying existing drake instance.');
        drake.destroy();
        drake = null; // Reset drake
    }

    const employeeList = document.getElementById('employees-list');
    const dropzones = Array.from(document.querySelectorAll('.dropzone'));
    console.log(`Found ${dropzones.length} dropzones for initialization.`);

    if (!employeeList || dropzones.length === 0) {
        console.error('Drag and drop initialization aborted: Required elements not found.');
        return;
    }

    const containers = [employeeList].concat(dropzones);
  
    drake = dragula(containers, {
        copy: (el, source) => source === employeeList,
        accepts: (el, target) => target !== employeeList && !target.classList.contains('employee-block'),
        removeOnSpill: false,
        revertOnSpill: true,
        mirrorContainer: document.body,
        moves: (el) => {
            el.classList.add('employee-block'); // Ensure the mirror gets the correct class
            return true;
          }
    });
  
  
    drake.on('drop', function(el, target, source, sibling) {
      if (target === employeeList) return;
  
      const employeeId = el.getAttribute('data-employee-id');
      const shiftTypeId = target.getAttribute('data-shift-type-id');
      const date = target.getAttribute('data-date');
      let action = source !== employeeList && source.classList.contains('dropzone') ? 'move' : 'add';
      let originalDate = action === 'move' ? source.getAttribute('data-date') : date;
      let originalShiftTypeId = action === 'move' ? source.getAttribute('data-shift-type-id') : shiftTypeId;
  
      updateSchedule(employeeId, shiftTypeId, date, action, originalDate, originalShiftTypeId);
  
      if (source === employeeList) {
        let clonedEl = el.cloneNode(true);
        const group = el.getAttribute('data-group');
        clonedEl.classList.add(`group-${group}`); // Apply group class to cloned element
        // Make sure to include the surname when setting the text content
        const employeeName = el.getAttribute('data-employee-name');
        const employeeSurname = el.getAttribute('data-employee-surname');
        clonedEl.textContent = `${employeeName} ${employeeSurname}`;
        target.appendChild(clonedEl);
        drake.containers.push(clonedEl);
      } else {
        target.appendChild(el);
      }
  
    });
  
  
  
    drake.on('drag', function(el) {
        console.log('Dragging', el);
    });
    

    drake.on('dragend', function(el) {
        const shadows = document.querySelectorAll('.gu-mirror, .gu-transit');
        shadows.forEach(shadow => shadow.remove());
    });

    function updateSchedule(employeeId, shiftTypeId, date, action, originalDate, originalShiftTypeId) {
        const url = `/update_schedule/`;
        const requestBody = JSON.stringify({
            employeeId: employeeId,
            shiftTypeId: shiftTypeId,
            date: date,
            action: action,
            originalDate: originalDate,
            originalShiftTypeId: originalShiftTypeId
        });
    
        console.log("Sending request with body:", requestBody);  // Debugging log
    
        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'), // Ensuring CSRF token is correctly fetched and included
            },
            body: requestBody,
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok: ' + response.statusText);
            }
            return response.json();
        })
        .then(data => {
            console.log('Success:', data); // Log success for debugging
        })
        .catch(error => {
            console.error('Error:', error); // Log any errors
        });
    }

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
          const cookies = document.cookie.split(';');
          for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
              cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
              break;
            }
          }
        }
        return cookieValue;
      }  

  // New functionality to fetch and render schedule on page load
  fetchAndRenderSchedule();
};

// Function to fetch schedule data and update the UI accordingly
function fetchAndRenderSchedule() {
    // Assuming your schedule grid has an attribute 'data-week-start' in ISO format
    let weekStart = moment.tz(document.getElementById('schedule-grid').getAttribute('data-week-start'), "Europe/Berlin");
    let weekEnd = weekStart.clone().add(6, 'days'); // Get the end of the week

    const startFormat = weekStart.format('YYYY-MM-DD');
    const endFormat = weekEnd.format('YYYY-MM-DD');

    fetch(`/api/schedule/?week_start=${startFormat}&week_end=${endFormat}`)
    .then(response => response.json())
    .then(data => {
        document.querySelectorAll('.dropzone').forEach(dz => dz.innerHTML = ''); // Clear existing blocks
        
        data.forEach(({ date, shift_type_id, employees }) => {
            const cell = document.querySelector(`.dropzone[data-shift-type-id="${shift_type_id}"][data-date="${date}"]`);
            if (!cell) {
                console.error('Dropzone not found for date:', date, 'and shift type ID:', shift_type_id);
                return; // Skip this iteration if the cell doesn't exist
            }
            employees.forEach(employee => {
                const employeeBlock = createEmployeeBlock(employee,date);
                cell.appendChild(employeeBlock);
            });
        });
        console.log('Schedule fetched and rendered successfully.');
    })
    .catch(error => console.error('Error fetching schedule:', error));
}



function createEmployeeBlock(employee, date) {
  if (employee.group === '1') return null;

  const div = document.createElement('div');
  div.className = `employee-block group-${employee.group}`;
  div.setAttribute('data-employee-id', employee.id);
  div.setAttribute('data-group', employee.group);

  // Add employee name and group
  const nameSpan = document.createElement('span');
  const nameInitial = employee.name ? employee.name.charAt(0).toUpperCase() : '';
  nameSpan.className = 'employee-name';
  nameSpan.textContent = `${employee.surname} ${nameInitial}. (${employee.group})`;
  div.appendChild(nameSpan);

  // Add cog button
  const cogButton = document.createElement('button');
  cogButton.className = 'cog-btn';
  cogButton.title = 'Unesite prekovremene sate';
  cogButton.innerHTML = '⚙️';
  cogButton.onclick = () => openOvertimeModal(employee.id, date);
  div.appendChild(cogButton);

  // Add delete button
  const deleteButton = document.createElement('button');
  deleteButton.className = 'delete-btn';
  deleteButton.textContent = '❌';
  deleteButton.onclick = () => deleteScheduleEntry(employee.id, date);
  div.appendChild(deleteButton);

  return div;
}



function openOvertimeModal(employeeId, date) {
  console.log(`Opening modal for Employee ID: ${employeeId}, Date: ${date}`);

  let employeeInput = document.getElementById('employee-id');
  let dateInput = document.getElementById('work-date');
  let modal = document.getElementById('overtime-dialog');
  
  if (!employeeInput || !dateInput || !modal) {
      console.error('Could not find one or more elements needed to open the modal.');
      return;
  }
  
  employeeInput.value = employeeId;
  dateInput.value = date;
  
  fetch(`/get_workday_data/?employee_id=${employeeId}&date=${date}`)
  .then(response => response.json())
  .then(data => {
      if (data.status === 'success') {
          document.getElementById('overtime-hours').value = data.data.overtime_hours || 0;
          document.getElementById('day-hours').value = data.data.day_hours || 0;
          document.getElementById('night-hours').value = data.data.night_hours || 0;
      } else {
          document.getElementById('overtime-hours').value = 0;
          document.getElementById('day-hours').value = 0;
          document.getElementById('night-hours').value = 0;
      }
      modal.classList.remove('hidden');
  })
  .catch(error => {
      console.error('Error fetching workday data:', error);
      document.getElementById('overtime-hours').value = 0;
      document.getElementById('day-hours').value = 0;
      document.getElementById('night-hours').value = 0;
      modal.classList.remove('hidden');
  });
}

function closeOvertimeDialog() {
  console.log('Closing modal');
  document.getElementById('overtime-dialog').classList.add('hidden');
}

function submitOvertime() {
  const employeeId = document.getElementById('employee-id').value;
  const date = document.getElementById('work-date').value;
  const overtimeHours = document.getElementById('overtime-hours').value;
  const dayHours = document.getElementById('day-hours').value;
  const nightHours = document.getElementById('night-hours').value;

  let requestData = { employee_id: employeeId, date: date };
  
  if (overtimeHours !== '') {
      requestData.overtime_hours = parseFloat(overtimeHours);
  }
  if (dayHours !== '') {
      requestData.day_hours = parseFloat(dayHours);
  }
  if (nightHours !== '') {
      requestData.night_hours = parseFloat(nightHours);
  }

  console.log("Submitting overtime with data:", requestData);

  fetch('/update_overtime_hours/', {
      method: 'POST',
      headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify(requestData)
  })
  .then(response => response.json())
  .then(data => {
      if (data.status === 'success') {
          closeOvertimeDialog();
          // Optionally, update the UI to reflect the new hours
      } else {
          console.error(data.error);
      }
  })
  .catch(error => {
      console.error('Error:', error);
  });
}

function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
          const cookie = cookies[i].trim();
          if (cookie.substring(0, name.length + 1) === (name + '=')) {
              cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
              break;
          }
      }
  }
  return cookieValue;
}

