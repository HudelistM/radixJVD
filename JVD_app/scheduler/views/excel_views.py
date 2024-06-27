# Excel imports
import xlsxwriter

from calendar import monthrange
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from datetime import date, timedelta
from ..models import ScheduleEntry, ShiftType, Employee, WorkDay, FixedHourFund, Holiday, ExcessHours
from io import BytesIO
import calendar
from django.contrib.auth.decorators import login_required

#--------------------------------------------------------------------------
#--------------------- Generiranje Excel datoteki -------------------------
#--------------------------------------------------------------------------

def get_week_dates(start_date):
    # start_date is assumed to be a Monday
    return [start_date + timedelta(days=i) for i in range(7)]


# Croatian day names to use for mapping
day_names_cro = {
    'Monday': 'Pon', 
    'Tuesday': 'Uto', 
    'Wednesday': 'Sri', 
    'Thursday': 'Čet', 
    'Friday': 'Pet', 
    'Saturday': 'Sub', 
    'Sunday': 'Ned'
}

def croatian_day(date_obj):
    """Return the Croatian day abbreviation for the date."""
    return day_names_cro[calendar.day_name[date_obj.weekday()]]


def create_schedule_excel(week_dates, shift_types, schedule_data, author_name):
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet()

    worksheet.set_landscape()
    worksheet.set_paper(9)
    worksheet.fit_to_pages(1, 1)

    # Define formats
    title_format = workbook.add_format({'bold': True, 'font_size': 18, 'align': 'center', 'valign': 'vcenter'})
    author_format = workbook.add_format({'font_size': 12, 'align': 'right', 'valign': 'vcenter'})
    header_format = workbook.add_format({'bold': True, 'bg_color': '#d9e1f2', 'align': 'center', 'valign': 'vcenter', 'text_wrap': True, 'border': 1})
    date_format = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_size': 14, 'border': 2})
    cell_format = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter'})
    saturday_date_format = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'bg_color': '#CCFFCC', 'font_size': 14})
    sunday_date_format = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'bg_color': '#FFFF99', 'font_size': 14})

    # Text color formats for groups
    group_text_formats = {
        '1': workbook.add_format({'color': '#1E8449'}),
        '2': workbook.add_format({'color': '#D35400'}),
        '3': workbook.add_format({'color': '#2980B9'}),
        # Add more groups as needed
    }

    # Set column widths
    worksheet.set_column(0, 0, 20)
    for idx, _ in enumerate(shift_types, 1):
        worksheet.set_column(idx, idx, 15)

    # Write title and author rows
    title = f"Weekly Schedule for {week_dates[0].strftime('%B')}"
    worksheet.merge_range('A1:H1', title, title_format)
    worksheet.merge_range('A2:H2', f"Made by: {author_name}", author_format)

    # Write header row
    headers = ['Dan Datum'] + [shift_type.name for shift_type in shift_types]
    worksheet.write_row('A3', headers, header_format)

    current_row = 3

    for date in week_dates:
        max_employees = 1
        for shift_type in shift_types:
            schedule_entry = schedule_data.get(date.strftime('%Y-%m-%d'), {}).get(shift_type.id)
            employees = schedule_entry.employees.all() if schedule_entry else []
            max_employees = max(max_employees, len(employees))

        # Determine row formatting for the date cell
        if date.weekday() == 5:  # Saturday
            date_cell_format = saturday_date_format
        elif date.weekday() == 6:  # Sunday
            date_cell_format = sunday_date_format
        else:
            date_cell_format = date_format

        # Merge the date cell dynamically
        merge_to = current_row + max_employees - 1
        worksheet.merge_range(current_row, 0, merge_to, 0, croatian_day(date) + ' ' + date.strftime('%d.%m.%Y.'), date_cell_format)

        for col_idx, shift_type in enumerate(shift_types, start=1):
            schedule_entry = schedule_data.get(date.strftime('%Y-%m-%d'), {}).get(shift_type.id)
            employees = schedule_entry.employees.all() if schedule_entry else []
            emp_blocks = [employees[i:i + 7] for i in range(0, len(employees), 7)]
            for block_idx, block in enumerate(emp_blocks):
                for emp_idx, employee in enumerate(block):
                    cell_value = f"{employee.name} {employee.surname}"
                    group_format = group_text_formats.get(employee.group)
                    zero_width_space = "\u200B"
                    if group_format:
                        worksheet.write_rich_string(current_row + emp_idx, col_idx + block_idx, zero_width_space, group_format, cell_value, cell_format)
                    else:
                        worksheet.write(current_row + emp_idx, col_idx + block_idx, cell_value, cell_format)

        current_row += max_employees or 1

    workbook.close()
    output.seek(0)
    return output



@login_required
def download_schedule(request):
    start_date_str = request.GET.get('week_start')
    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    else:
        today = date.today()
        start_date = today - timedelta(days=today.weekday())

    week_dates = get_week_dates(start_date)
    shift_types = ShiftType.objects.all()

    schedule_data = {}
    for day in week_dates:
        schedule_data[day.strftime('%Y-%m-%d')] = {}
        for shift_type in shift_types:
            schedule_entry = ScheduleEntry.objects.filter(
                date=day, shift_type=shift_type
            ).first()
            schedule_data[day.strftime('%Y-%m-%d')][shift_type.id] = schedule_entry

    author_name = request.user.username

    excel_file = create_schedule_excel(week_dates, shift_types, schedule_data, author_name)

    response = HttpResponse(content=excel_file.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="schedule.xlsx"'
    return response

@login_required
def download_sihterica(request):
    # Define Croatian month names
    croatian_months = {
        1: 'Siječanj', 2: 'Veljača', 3: 'Ožujak',
        4: 'Travanj', 5: 'Svibanj', 6: 'Lipanj',
        7: 'Srpanj', 8: 'Kolovoz', 9: 'Rujan',
        10: 'Listopad', 11: 'Studeni', 12: 'Prosinac'
    }

    # Extract current month and year for the title
    current_date = date.today()
    current_month = current_date.month  # Use the month's numeric value directly
    current_year = current_date.year
    days_in_month = monthrange(current_year, current_month)[1]
    
    employees = Employee.objects.all().order_by('group')
    
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet()

    # Set up formats
    title_format = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_size': 16})
    bold_format = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_size': 12})
    header_format = workbook.add_format({'align': 'center', 'bold': True, 'bg_color': '#f0f0f0'})
    total_format = workbook.add_format({'align': 'center', 'bg_color': '#d9e1f2'})
    hours_format = workbook.add_format({'align': 'center'})
    saturday_format = workbook.add_format({'align': 'center', 'bg_color': '#CCFFCC'})  # Green
    sunday_format = workbook.add_format({'align': 'center', 'bg_color': '#FFFF99'})  # Yellow
    gray_format = workbook.add_format({'bg_color': '#E0E0E0', 'align': 'center'})  # Gray
    white_format = workbook.add_format({'bg_color': '#FFFFFF', 'align': 'center'})  # White
    vacation_format = workbook.add_format({'align': 'center',  'font_color': '#00FF00'})
    total_vacation_format = workbook.add_format({'align': 'center','font_color': '#00FF00', 'bg_color': '#d9e1f2'})


    # Group text color formats
    group_text_formats = {
        '1': workbook.add_format({'color': '#1E8449', 'align': 'center', 'valign': 'vcenter', 'font_size': 12, 'bold': True}),
        '2': workbook.add_format({'color': '#D35400', 'align': 'center', 'valign': 'vcenter', 'font_size': 12, 'bold': True}),
        '3': workbook.add_format({'color': '#2980B9', 'align': 'center', 'valign': 'vcenter', 'font_size': 12, 'bold': True}),
    }
    


    # Set column widths
    worksheet.set_column(0, 0, 20)  # Employee names
    worksheet.set_column(1, 1, 3)    # RD/RN column
    worksheet.set_column(2, 33, 4)   # Day columns
    worksheet.set_column(34, 43, 10) # Aggregate columns

    # Add title row
    month_name = croatian_months[current_month]
    title = f"Evidencija prisutnosti na radu za mjesec {month_name} {current_year}"
    worksheet.merge_range(0, 0, 0, 42, title, title_format)

    # Add headers
    worksheet.merge_range(1, 0, 2, 0, 'Prezime i ime', header_format)

    # Day abbreviations for each day of the week (Monday to Sunday)
    day_abbreviations = ['P', 'U', 'S', 'Č', 'P', 'S', 'N']
    for day in range(1, days_in_month + 1):
        weekday = date(year=current_year, month=current_date.month, day=day).weekday()
        format_to_use = saturday_format if weekday == 5 else sunday_format if weekday == 6 else header_format
        worksheet.write(1, day + 1, day_abbreviations[weekday], format_to_use)
        worksheet.write(2, day + 1, str(day), format_to_use)

    worksheet.merge_range(1, 34, 2, 34, 'Fond sati', total_format)
    worksheet.merge_range(1, 35, 2, 35, 'Regularni rad', total_format)
    worksheet.merge_range(1, 36, 2, 36, 'Turnus', total_format)
    worksheet.merge_range(1, 37, 2, 37, 'Višak fonda', total_format)
    worksheet.merge_range(1, 38, 2, 38, 'Subota', total_format)
    worksheet.merge_range(1, 39, 2, 39, 'Nedjelja', total_format)
    worksheet.merge_range(1, 40, 2, 40, 'Noćni rad', total_format)
    worksheet.merge_range(1, 41, 2, 41, 'Blagdan', total_format)
    worksheet.merge_range(1, 42, 2, 42, 'Bolovanje', total_format)
    worksheet.merge_range(1, 43, 2, 43, 'Godišnji odmor', total_format)

    # Fill employee data
    row_idx = 3

    for employee in employees:
        group_format = group_text_formats.get(employee.group, bold_format)
        worksheet.merge_range(row_idx, 0, row_idx + 1, 0, f"{employee.name} {employee.surname}", group_format)
        worksheet.write(row_idx, 1, 'RD', bold_format)
        worksheet.write(row_idx + 1, 1, 'RN', bold_format)

        # Initialize aggregates
        total_day_hours = total_night_hours = total_saturday_hours = 0
        total_sunday_hours = total_holiday_hours = total_sick_leave_hours = 0
        total_vacation_hours = WorkDay.objects.filter(employee=employee, vacation_hours__gt=0).aggregate(Sum('vacation_hours'))['vacation_hours__sum'] or 0

        # Iterate over each day of the month
        for day in range(1, days_in_month + 1):
            current_date = date(year=current_year, month=current_month, day=day)
            work_days = WorkDay.objects.filter(employee=employee, date=current_date)  # Fetch all workdays for the date
            weekday = current_date.weekday()
            base_cell_format = saturday_format if weekday == 5 else sunday_format if weekday == 6 else hours_format

            if work_days.exists():
                total_day_hours_for_day = sum(work_day.day_hours for work_day in work_days)
                total_night_hours_for_day = sum(work_day.night_hours for work_day in work_days)
                total_vacation_hours_for_day = sum(work_day.vacation_hours for work_day in work_days)

                day_hours_display = total_day_hours_for_day if total_day_hours_for_day != 0 else ''
                night_hours_display = total_night_hours_for_day if total_night_hours_for_day != 0 else ''

                # Apply green text for vacation only on the 'RD' row and maintain weekend formatting
                if total_vacation_hours_for_day > 0:
                    worksheet.write(row_idx, day + 1, '0', vacation_format)  # Green zero for RD row
                    worksheet.write(row_idx + 1, day + 1, night_hours_display, base_cell_format)  # Normal formatting for RN row
                else:
                    worksheet.write(row_idx, day + 1, day_hours_display, base_cell_format)
                    worksheet.write(row_idx + 1, day + 1, night_hours_display, base_cell_format)

                # Update aggregates
                total_day_hours += total_day_hours_for_day
                total_night_hours += total_night_hours_for_day
                if weekday == 5:
                    total_saturday_hours += total_day_hours_for_day
                elif weekday == 6:
                    total_sunday_hours += total_day_hours_for_day
                total_holiday_hours += sum(work_day.holiday_hours for work_day in work_days)
                total_sick_leave_hours += sum(work_day.sick_leave_hours for work_day in work_days)
            else:
                worksheet.write(row_idx, day + 1, '', base_cell_format)
                worksheet.write(row_idx + 1, day + 1, '', base_cell_format)

        # Load or calculate hourly funds
        try:
            hour_fund = FixedHourFund.objects.get(month__year=current_year, month__month=current_month).required_hours
        except FixedHourFund.DoesNotExist:
            hour_fund = 168  # Default or error handling scenario

        redovan_rad = employee.calculate_redovan_rad(current_month, current_year)
        turnus = employee.calculate_monthly_hours(current_month, current_year)
        visak_sati = employee.calculate_visak_sati(current_month, current_year)

        # Fill in the aggregate data
        worksheet.merge_range(row_idx, 34, row_idx + 1, 34, hour_fund, total_format)
        worksheet.merge_range(row_idx, 35, row_idx + 1, 35, redovan_rad, total_format)
        worksheet.merge_range(row_idx, 36, row_idx + 1, 36, turnus, total_format)
        worksheet.merge_range(row_idx, 37, row_idx + 1, 37, visak_sati, total_format)
        worksheet.merge_range(row_idx, 38, row_idx + 1, 38, total_saturday_hours, total_format)
        worksheet.merge_range(row_idx, 39, row_idx + 1, 39, total_sunday_hours, total_format)
        worksheet.merge_range(row_idx, 40, row_idx + 1, 40, total_night_hours, total_format)
        worksheet.merge_range(row_idx, 41, row_idx + 1, 41, total_holiday_hours, total_format)
        worksheet.merge_range(row_idx, 42, row_idx + 1, 42, total_sick_leave_hours, total_format)
        worksheet.merge_range(row_idx, 43, row_idx + 1, 43, total_vacation_hours, total_vacation_format)

        row_idx += 2
        
    #-----------------------Aggregate table for total overview----------------------------
    worksheet.set_column(34,34,14)
    worksheet.set_column(35, 50, 12)  # Adjusted to column AX
    # First aggregate table start
    agg_start_row = row_idx + 2
    agg_start_col = 34
    
    # Title for the first aggregate table
    worksheet.merge_range(agg_start_row, agg_start_col, agg_start_row, agg_start_col + 15, f'Ukupni sati za {month_name} {current_year}', title_format)
    agg_start_row += 1

    # Add first aggregate table headers
    aggregate_headers = ['Ime i Prezime', 'rb.', 'Fond sati', 'Red. rad', 'Drž. pr. i bla.', 'Godišnji o.', 'Bolovanje', 'Noćni rad',
                         'Rad sub.', 'Rad. ned.', 'Slobodan dan', 'Turnus', 'Priprema', 'Prek.rad', 'Prek. USLUGA', 'Prek. Višak Fonda']

    small_header_format = workbook.add_format({'align': 'center', 'bold': True, 'font_size': 9, 'bg_color': '#f0f0f0'})

    for i, header in enumerate(aggregate_headers):
        worksheet.write(agg_start_row, agg_start_col + i, header, small_header_format)

    agg_start_row += 1

    

    # Add first aggregate data
    for idx, employee in enumerate(employees):
        work_days = WorkDay.objects.filter(employee=employee, date__year=current_year, date__month=current_date.month)
        total_vacation_hours = sum(day.vacation_hours for day in work_days)
        total_sick_leave_hours = sum(day.sick_leave_hours for day in work_days)
        total_holiday_hours = sum(day.holiday_hours for day in work_days)
        total_day_hours = sum(day.day_hours for day in work_days)
        total_night_hours = sum(day.night_hours for day in work_days)
        total_saturday_hours = sum(day.saturday_hours for day in work_days)
        total_sunday_hours = sum(day.sunday_hours for day in work_days)
        total_on_call_hours = sum(day.on_call_hours for day in work_days)
        total_overtime_hours = sum(day.overtime_hours for day in work_days)
        total_free_days_hours = 0  # Replace placeholder with actual calculation

        row_format = gray_format if idx % 2 == 0 else white_format
        
        worksheet.write(agg_start_row, agg_start_col, f"{employee.name} {employee.surname}", row_format)
        worksheet.write(agg_start_row, agg_start_col+1, idx + 1, row_format)
        worksheet.write(agg_start_row, agg_start_col+2, hour_fund, row_format)
        worksheet.write(agg_start_row, agg_start_col+3, total_day_hours, row_format)
        worksheet.write(agg_start_row, agg_start_col+4, total_holiday_hours, row_format)
        worksheet.write(agg_start_row, agg_start_col+5, total_vacation_hours, row_format)
        worksheet.write(agg_start_row, agg_start_col+6, total_sick_leave_hours, row_format)
        worksheet.write(agg_start_row, agg_start_col+7, total_night_hours, row_format)
        worksheet.write(agg_start_row, agg_start_col+8, total_saturday_hours, row_format)
        worksheet.write(agg_start_row, agg_start_col+9, total_sunday_hours, row_format)
        worksheet.write(agg_start_row, agg_start_col+10, total_free_days_hours, row_format)
        worksheet.write(agg_start_row, agg_start_col+11, total_day_hours + total_night_hours, row_format)
        worksheet.write(agg_start_row, agg_start_col+12, total_on_call_hours, row_format)
        worksheet.write(agg_start_row, agg_start_col+13, total_overtime_hours, row_format)
        worksheet.write(agg_start_row, agg_start_col+14, 0, row_format)  # Prek. USLUGA
        worksheet.write(agg_start_row, agg_start_col+15, 0, row_format)  # Prek. Višak Fonda

        agg_start_row += 1

    # Add "Ukupno" row for the first aggregate table
    first_data_row = agg_start_row - len(employees)  # This should be the row index where your first data entry starts
    last_data_row = agg_start_row  # The row before the aggregate starts

    # Add "Ukupno" title in the first column of the total row
    worksheet.write(last_data_row , agg_start_col, 'Ukupno', header_format)

    # Writing sum formulas directly below the last data entry
    for col_num in range(36, 50):  # Adjusting the column range for sum
        column_letter_value = column_letter(col_num + 1)  # Using a helper function for Excel column letters
        formula_range = f"{column_letter_value}{first_data_row}:{column_letter_value}{last_data_row}"
        worksheet.write_formula(last_data_row, col_num, f"=SUM({formula_range})", total_format)

    total_preparation_overtime=0


   #-----------------------Aggregate table for sati pripreme-----------------------------
   
   
    first_day_of_month = date(current_year, current_month, 1)
    last_day_of_month = date(current_year, current_month, calendar.monthrange(current_year, current_month)[1])
    weeks = {((first_day_of_month + timedelta(days=x)).isocalendar()[1]) for x in range((last_day_of_month - first_day_of_month).days + 1)}

    # Start the second aggregate table
    agg_start_row += 3  # Space after the first aggregate table
    title_row = agg_start_row
    worksheet.merge_range(title_row, 0, title_row, 9, 'BROJ SATI PRIPREME', title_format)
    agg_start_row += 1

    # Calculate the number of weeks in the current month
    first_day_of_month = date(current_year, current_month, 1)
    last_day_of_month = date(current_year, current_month, calendar.monthrange(current_year, current_month)[1])
    weeks = {((first_day_of_month + timedelta(days=x)).isocalendar()[1]) for x in range((last_day_of_month - first_day_of_month).days + 1)}
    num_weeks = len(weeks)

    # Ensure not to overlap with already merged title
    worksheet.write(agg_start_row, 0, 'Ime i Prezime', header_format)
    worksheet.write(agg_start_row, 1, 'rb.', header_format)

    # Merging the week columns under one header 'Prip. iz rasporeda'
    start_week_col = 2
    end_week_col = start_week_col + num_weeks - 1  # Determine the last column index for weeks

    # Correct merging by ensuring it does not overlap with previous merges
    if title_row == agg_start_row:
        worksheet.merge_range(title_row + 1, start_week_col, title_row + 1, end_week_col, 'Prip. iz rasporeda', header_format)
    else:
        worksheet.merge_range(agg_start_row, start_week_col, agg_start_row, end_week_col, 'Prip. iz rasporeda', header_format)

    # Headers for other columns
    worksheet.write(agg_start_row, end_week_col + 1, 'Priprema um. prekovremene', header_format)
    worksheet.write(agg_start_row, end_week_col + 2, 'Ukupno', header_format)

    agg_start_row += 1  # Move to the next row to start adding weekly data

    for idx, employee in enumerate(employees):
        worksheet.write(agg_start_row, 0, f"{employee.name} {employee.surname}", row_format)
        worksheet.write(agg_start_row, 1, idx + 1, row_format)
        col_offset = 2  # Starting column for week data
        total_weekly_hours = 0  # Reset for each employee
        for week_num in sorted(weeks):
            week_days = [first_day_of_month + timedelta(days=x) for x in range((last_day_of_month - first_day_of_month).days + 1) if (first_day_of_month + timedelta(days=x)).isocalendar()[1] == week_num]
            weekly_hours = sum(WorkDay.objects.filter(employee=employee, date__in=week_days).values_list('on_call_hours', flat=True))
            worksheet.write(agg_start_row, col_offset, weekly_hours, row_format)
            total_weekly_hours += weekly_hours  # Accumulate for total
            col_offset += 1
        # Correct the total column position
        worksheet.write(agg_start_row, col_offset, total_preparation_overtime, row_format)
        worksheet.write(agg_start_row, col_offset + 1, total_weekly_hours, row_format)  # Corrected position for total

        agg_start_row += 1
    
    #-----------------------Aggregate table for višak manjak sati-----------------------------
    
    # Calculate the cumulative excess up to the last month
    previous_month = current_month - 1 if current_month > 1 else 12
    previous_year = current_year if current_month > 1 else current_year - 1
    last_day_of_previous_month = monthrange(previous_year, previous_month)[1]
    previous_month_header = f"Fond sati s {last_day_of_previous_month}.{previous_month}"

    current_month_excess_header = f"Višak fonda ({croatian_months[current_month]} {current_year})"
    last_day_of_current_month = monthrange(current_year, current_month)[1]
    current_month_header = f"Fond sati s {last_day_of_current_month}.{current_month}"

    # Begin writing the table for cumulative excess
    worksheet.merge_range(agg_start_row, agg_start_col, agg_start_row, agg_start_col+4, 'EVIDENCIJA VIŠKA-MANJKA SATI', title_format)
    sub_headers = ['PREZIME I IME', 'rb', previous_month_header, current_month_excess_header, current_month_header]
    worksheet.write_row(agg_start_row + 1, agg_start_col, sub_headers, small_header_format)
    agg_start_row += 2

    # Populate the table with the correct excess hours calculations
    for idx, employee in enumerate(employees):
        # Fetch the previous month's cumulative excess from the database
        try:
            previous_excess_record = ExcessHours.objects.get(employee=employee, year=previous_year, month=previous_month)
            previous_excess = previous_excess_record.excess_hours
        except ExcessHours.DoesNotExist:
            previous_excess = 0  # Handle the case where no record exists

        # Calculate the current month's excess
        current_excess = employee.calculate_visak_sati(current_month, current_year)
        cumulative_excess_current_month = previous_excess + current_excess

        worksheet.write(agg_start_row, agg_start_col, f"{employee.surname} {employee.name}", white_format)
        worksheet.write(agg_start_row, agg_start_col+1, idx + 1, white_format)
        worksheet.write(agg_start_row, agg_start_col+2, previous_excess, hours_format)
        worksheet.write(agg_start_row, agg_start_col+3, current_excess, hours_format)
        worksheet.write(agg_start_row, agg_start_col+4, cumulative_excess_current_month, hours_format)

        agg_start_row += 1
        
        # Aggregate table for vacation data
    agg_vacation_start_row = agg_start_row + 2  # Space after the last table

    previous_month_header = f"GO s {last_day_of_previous_month}.{previous_month}.{previous_year}"
    current_month_header_hours = f"GO sati ({croatian_months[current_month]} {current_year})"
    current_month_header_days = f"GO dani ({croatian_months[current_month]} {current_year})"
    previous_month_header = f"GO s {last_day_of_previous_month}.{previous_month}.{previous_year}"

    worksheet.merge_range(agg_vacation_start_row, agg_start_col, agg_vacation_start_row, agg_start_col+4, 'EVIDENCIJA GODIŠNJIH ODMORA', title_format)
    vacation_headers = ['Prezime i ime', previous_month_header, current_month_header_hours, current_month_header_days, previous_month_header]
    worksheet.write_row(agg_vacation_start_row + 1, agg_start_col, vacation_headers, small_header_format)
    agg_vacation_start_row += 2

    # Populate the table
    for idx, employee in enumerate(employees):
        # Retrieve vacation data from ExcessHours for previous month
        previous_month = current_month - 1 if current_month > 1 else 12
        previous_year = current_year if current_month > 1 else current_year - 1
        previous_vacation_record = ExcessHours.objects.filter(employee=employee, year=previous_year, month=previous_month).first()
        previous_vacation_hours = previous_vacation_record.vacation_hours_used if previous_vacation_record else 0

        # Current month vacation hours and calculation to days
        current_vacation_hours = WorkDay.objects.filter(employee=employee, date__year=current_year, date__month=current_month).aggregate(Sum('vacation_hours'))['vacation_hours__sum'] or 0
        current_vacation_days = current_vacation_hours / 8  # Assuming 8 hours per day for conversion to days

        # Calculate new cumulative vacation hours and convert to days
        new_cumulative_vacation_hours = previous_vacation_hours + current_vacation_hours
        new_cumulative_vacation_days = new_cumulative_vacation_hours / 8

        # Write data to the worksheet
        worksheet.write(agg_vacation_start_row, agg_start_col, f"{employee.surname} {employee.name}", white_format)
        worksheet.write(agg_vacation_start_row, agg_start_col+1, previous_vacation_hours / 8, hours_format)  # Previous month cumulative in days
        worksheet.write(agg_vacation_start_row, agg_start_col+2, current_vacation_hours, hours_format)
        worksheet.write(agg_vacation_start_row, agg_start_col+3, current_vacation_days, hours_format)
        worksheet.write(agg_vacation_start_row, agg_start_col+4, new_cumulative_vacation_days, hours_format)  # New cumulative in days

        agg_vacation_start_row += 1
        
    # -----------------------Aggregate table for overtime hours-----------------------------

    agg_overtime_start_row = agg_vacation_start_row + 2  # Space after the vacation table

    # Headers for the overtime hours table
    overtime_headers = [
        'Prezime i ime', 'rb', 'Prek. pripreme', 'Prek. USLUGA priprema', 
        'Prek. višak fonda', 'Prekovremeno slobodan dan', 
        'Prekovremeno slobodan dan usluga', 'Ukupno prek.', 'Ukupno prek. USLUGA'
    ]
    worksheet.merge_range(
        agg_overtime_start_row, agg_start_col, agg_overtime_start_row, 
        agg_start_col + len(overtime_headers) - 1, 'EVIDENCIJA PREKOVREMENIH SATI', title_format
    )
    worksheet.write_row(agg_overtime_start_row + 1, agg_start_col, overtime_headers, small_header_format)
    agg_overtime_start_row += 2

    # Populate the overtime hours table
    for idx, employee in enumerate(employees):
        # Retrieve overtime data for the current month
        work_days = WorkDay.objects.filter(employee=employee, date__year=current_year, date__month=current_month)
        total_overtime_preparation = work_days.aggregate(Sum('overtime_hours'))['overtime_hours__sum'] or 0
        total_overtime_service = work_days.aggregate(Sum('overtime_service'))['overtime_service__sum'] or 0
        total_overtime_excess_fond = work_days.aggregate(Sum('overtime_excess_fond'))['overtime_excess_fond__sum'] or 0
        total_overtime_free_day = work_days.aggregate(Sum('overtime_free_day'))['overtime_free_day__sum'] or 0
        total_overtime_free_day_service = work_days.aggregate(Sum('overtime_free_day_service'))['overtime_free_day_service__sum'] or 0

        # Calculate total overtime
        total_overtime = total_overtime_preparation + total_overtime_service + total_overtime_excess_fond
        total_overtime_service_total = total_overtime_free_day + total_overtime_free_day_service

        worksheet.write(agg_overtime_start_row, agg_start_col, f"{employee.surname} {employee.name}", white_format)
        worksheet.write(agg_overtime_start_row, agg_start_col + 1, idx + 1, white_format)
        worksheet.write(agg_overtime_start_row, agg_start_col + 2, total_overtime_preparation, hours_format)
        worksheet.write(agg_overtime_start_row, agg_start_col + 3, total_overtime_service, hours_format)
        worksheet.write(agg_overtime_start_row, agg_start_col + 4, total_overtime_excess_fond, hours_format)
        worksheet.write(agg_overtime_start_row, agg_start_col + 5, total_overtime_free_day, hours_format)
        worksheet.write(agg_overtime_start_row, agg_start_col + 6, total_overtime_free_day_service, hours_format)
        worksheet.write(agg_overtime_start_row, agg_start_col + 7, total_overtime, hours_format)
        worksheet.write(agg_overtime_start_row, agg_start_col + 8, total_overtime_service_total, hours_format)

        agg_overtime_start_row += 1

    # Add "Ukupno" row for the overtime table
    first_overtime_data_row = agg_overtime_start_row - len(employees)
    worksheet.write(agg_overtime_start_row, agg_start_col, 'Ukupno', header_format)

    # Writing sum formulas for the overtime table
    for col_offset in range(1, 10):  # Adjust column range to match the new overtime columns
        column_letter_value = column_letter(agg_start_col + col_offset)
        formula_range = f"{column_letter_value}{first_overtime_data_row + 1}:{column_letter_value}{agg_overtime_start_row}"
        worksheet.write_formula(agg_overtime_start_row, agg_start_col + col_offset, f"=SUM({formula_range})", total_format)


    workbook.close()
    output.seek(0)

    response = HttpResponse(content=output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="sihterica.xlsx"'
    return response

def column_letter(index):
    """ Convert column index to Excel-style column letter (1-indexed). """
    index -= 1  # Adjusting from 1-indexed to 0-indexed
    result = ''
    while index >= 0:
        result = chr(index % 26 + 65) + result
        index = index // 26 - 1
    return result