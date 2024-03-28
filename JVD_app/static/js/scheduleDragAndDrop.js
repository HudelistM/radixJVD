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
    });
  
    const employeeAssignments = new Map();
  
    drake.on('drop', function(el, target, source, sibling) {
      if (target === employeeList) return;
  
      const employeeId = el.getAttribute('data-employee-id');
      const shiftTypeId = target.getAttribute('data-shift-type-id');
      const date = target.getAttribute('data-date');
      let action = source !== employeeList && source.classList.contains('dropzone') ? 'move' : 'add';
  
      updateSchedule(employeeId, shiftTypeId, date, action);
  
      if (source === employeeList) {
        let clonedEl = el.cloneNode(true);
        clonedEl.classList.add('hide-counter');
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
  
      let count = employeeAssignments.get(employeeId) || 0;
      count = action === 'add' ? ++count : count;
      employeeAssignments.set(employeeId, count);
      updateEmployeeBlockCounter(employeeId, count);
    });
  
    drake.on('drag', function(el) {
        console.log('Dragging', el);
    });
    

    drake.on('dragend', function(el) {
        const shadows = document.querySelectorAll('.gu-mirror, .gu-transit');
        shadows.forEach(shadow => shadow.remove());
    });

    function updateSchedule(employeeId, shiftTypeId, date, action) {
        const url = `/update_schedule/`;
        // Construct the request body including the action parameter
        const requestBody = JSON.stringify({ employeeId, shiftTypeId, date, action });
        console.log("Sending request with body:", requestBody); // Logging the request body to debug
    
        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'), // Ensure CSRF token is correctly fetched and included
            },
            body: requestBody, // Use the requestBody that includes the action
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok: ' + response.statusText);
            }
            return response.json();
        })
        .then(data => {
            console.log('Success:', data); // Logging the success response
        })
        .catch(error => {
            console.error('Error:', error); // Logging any error that occurs during the fetch operation
        });
    }


  function getCookie(name) {
      let cookieValue = null;
      if (document.cookie && document.cookie !== '') {
          const cookies = document.cookie.split(';');
          for (let i = 0; i < cookies.length; i++) {
              const cookie = cookies[i].trim();
              if (cookie.substring(0, name.length + 1) === (name + '='))
                  cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                  break;
          }
      }
      return cookieValue;
  }

  function incrementAssignments(employeeId) {
      let count = employeeAssignments.get(employeeId) || 0;
      count++;
      employeeAssignments.set(employeeId, count);
      return count;
  }

  function updateEmployeeBlockCounter(employeeId, count) {
    const employeeBlock = employeeList.querySelector(`[data-employee-id="${employeeId}"]`);
    if (!employeeBlock) {
        console.error(`Employee block not found for employeeId: ${employeeId}`);
        return; // Exit the function if no employeeBlock is found
    }
    let counter = employeeBlock.querySelector('.drop-counter');
    if (!counter) {
        counter = document.createElement('span');
        counter.className = 'drop-counter';
        employeeBlock.appendChild(counter);
    }
    counter.innerText = count; // Display count without "/7"
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
                const employeeBlock = createEmployeeBlock(employee);
                cell.appendChild(employeeBlock);
            });
        });
        console.log('Schedule fetched and rendered successfully.');
    })
    .catch(error => console.error('Error fetching schedule:', error));
}



function createEmployeeBlock(employee) {
    const div = document.createElement('div');
    div.className = `employee-block group-${employee.group}`;
    div.setAttribute('data-employee-id', employee.id);
    div.setAttribute('data-group', employee.group);
    div.textContent = `${employee.name} ${employee.surname}`;
    return div;
}

