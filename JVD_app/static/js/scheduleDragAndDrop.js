document.addEventListener('DOMContentLoaded', function initDragAndDrop() {
  const employeeList = document.getElementById('employees-list');
  const dropzones = Array.from(document.querySelectorAll('.dropzone'));
  const containers = [employeeList].concat(dropzones);
  
  const drake = dragula(containers, {
      copy: (el, source) => source === employeeList,
      accepts: (el, target) => target !== employeeList && !target.classList.contains('employee-block'),
      removeOnSpill: false,
      revertOnSpill: true,
      mirrorContainer: document.body,
  });

  const employeeAssignments = new Map();

  drake.on('drop', function (el, target, source, sibling) {
    // Exiting early if the element is moving within the schedule
    if (source !== employeeList && target !== employeeList) {
      return; // This was a move, not a new clone, no need to increment the counter
    }
  
    if (target !== employeeList) {
      const employeeId = el.getAttribute('data-employee-id');
      let count = employeeAssignments.get(employeeId) || 0;
  
      // Only increment counter and clone if the source is the employee list
      if (source === employeeList) {
        if (count < 7) {
          count = incrementAssignments(employeeId);
  
          let clonedEl = el.cloneNode(true);
          clonedEl.classList.add('hide-counter'); // Intended to hide counter
          target.appendChild(clonedEl);
          drake.containers.push(clonedEl);
          updateEmployeeBlockCounter(employeeId, count);
        } else {
          alert("Maximum drops reached for this employee.");
          drake.cancel(true);
        }
      }
      const shiftTypeId = target.getAttribute('data-shift-type-id');
      const date = target.getAttribute('data-date');
      console.log({employeeId, shiftTypeId, date});
      // Call the function to update the backend
      updateSchedule(employeeId, shiftTypeId, date);
      console.log({employeeId, shiftTypeId, date});
    }
  });
  
  
  function updateSchedule(employeeId, shiftTypeId, date) {
    fetch('/update_schedule/', { // Replace '/update_schedule/' with the correct URL
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken'), // Ensure CSRF token is correctly handled
        },
        body: JSON.stringify({employeeId, shiftTypeId, date}),
    })
    .then(response => response.json())
    .then(data => {
        console.log('Success:', data);
    })
    .catch((error) => {
        console.error('Error:', error);
    });
}

// Function to get CSRF token from cookies
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

  function incrementAssignments(employeeId) {
      let count = employeeAssignments.get(employeeId) || 0;
      count++;
      employeeAssignments.set(employeeId, count);
      return count;
  }

  function updateEmployeeBlockCounter(employeeId, count) {
      // Find the employee block in the list and update its counter
      const employeeBlock = employeeList.querySelector(`[data-employee-id="${employeeId}"]`);
      let counter = employeeBlock.querySelector('.drop-counter');
      if (!counter) {
          counter = document.createElement('span');
          counter.className = 'drop-counter'; // Ensure this class is styled in your CSS
          employeeBlock.appendChild(counter);
      }
      counter.innerText = `${count}/7`;
  }

  drake.on('dragend', function(el) {
    // Clean up any leftover shadow elements
    const shadows = document.querySelectorAll('.gu-mirror, .gu-transit');
    shadows.forEach(function(shadow) {
        shadow.remove();
    });
  });
});