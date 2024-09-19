# Excel imports
import xlsxwriter
from django.contrib.staticfiles import finders

from calendar import monthrange
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from datetime import date, timedelta, datetime
from ..models import ScheduleEntry, ShiftType, Employee, WorkDay, FixedHourFund, Holiday, ExcessHours
from io import BytesIO
import calendar
from django.contrib.auth.decorators import login_required

import openpyxl
from datetime import timedelta, datetime
from openpyxl.utils import get_column_letter

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


def fill_dates_in_template(wb, start_date, month_start_points):
    sheet = wb.active
    
    # Get the Monday of the week where the month starts
    monday = start_date - timedelta(days=start_date.weekday())

    for mini_table_start in month_start_points:
        current_day = monday
        for row in range(mini_table_start, mini_table_start + 49, 7):  # Each table spans 7 rows for each day
            # B column pattern
            sheet[f"B{row}"] = croatian_day(current_day)  # Day of the week (e.g., "PON")
            sheet[f"B{row+1}"] = current_day.strftime('%d/%m')  # Day/Month
            sheet[f"B{row+2}"] = current_day.year  # Year

            current_day += timedelta(days=1)  # Move to the next day

def fill_employees_in_template(wb, schedule_data, week_dates):
    sheet = wb.active

    # Define column mappings to shift types
    shift_columns = {
        '1.smjena': 'C',
        '2.smjena': 'D',
        'Priprema od 19': 'E',
        'JANAF 1.smjena': 'F',
        'JANAF 2.smjena': 'F',
        'Slobodan Dan 1': 'G',
        'Slobodan Dan 2': 'H',
        'Godišnji odmor': 'I',
        'Bolovanje': 'J',
        '1.smjena INA': 'K',
        '2.smjena INA': 'L',
    }

    # Define row start positions based on day number (1st day starts at row 7, 2nd at 14, etc.)
    row_starts = {
        0: 7,  # Day 1 (Monday) starts at row 7
        1: 14, # Day 2 (Tuesday) starts at row 14
        2: 21, # Day 3 (Wednesday) starts at row 21
        3: 28, # Day 4 (Thursday) starts at row 28
        4: 35, # Day 5 (Friday) starts at row 35
        5: 42, # Day 6 (Saturday) starts at row 42
        6: 49  # Day 7 (Sunday) starts at row 49
    }

    for day_idx, day in enumerate(week_dates):
        day_str = day.strftime('%Y-%m-%d')
        if day_str in schedule_data:
            for shift_type_id, entry in schedule_data[day_str].items():
                if entry and entry.employees:
                    shift_type = ShiftType.objects.get(id=shift_type_id)
                    shift_column = shift_columns.get(shift_type.name, None)

                    if not shift_column:
                        continue  # Skip if shift column isn't defined

                    # Special handling for JANAF and Slobodan Dan
                    if shift_type.name in ['JANAF 1.smjena', 'JANAF 2.smjena']:
                        if shift_type.name == 'JANAF 1.smjena':
                            # JANAF 1.smjena: first shift rows (6 and 7) or (13 and 14)
                            rows = [6, 7] if day_idx % 2 == 0 else [13, 14]
                        else:
                            # JANAF 2.smjena: second shift rows (9, 10, 11) or (16, 17, 18)
                            rows = [9, 10, 11] if day_idx % 2 == 0 else [16, 17, 18]

                        for idx, employee in enumerate(entry.employees.all()):
                            if idx < len(rows):  # Fill only if within the row limits
                                sheet[f"{shift_column}{rows[idx]}"] = f"{employee.surname} {employee.name[0]}."

                    elif shift_type.name in ['Slobodan Dan 1', 'Slobodan Dan 2']:
                        # Slobodan Dan: fill from row 5 to row 11
                        rows = list(range(5, 12))
                        for idx, employee in enumerate(entry.employees.all()):
                            if idx < len(rows):
                                sheet[f"{shift_column}{rows[idx]}"] = f"{employee.surname} {employee.name[0]}."

                    else:
                        # General shifts (1.smjena, 2.smjena, etc.): fill normally starting from row 7, 14, etc.
                        row_start = row_starts.get(day_idx, 7)
                        for idx, employee in enumerate(entry.employees.all()):
                            sheet[f"{shift_column}{row_start + idx}"] = f"{employee.surname} {employee.name[0]}."



def create_schedule_excel(week_dates, shift_types, schedule_data, author_name):
    # Use Django staticfiles finders to locate the Excel template
    template_path = finders.find('template/RASPORED_template.xlsx')
    
    if not template_path:
        raise FileNotFoundError("The Excel template file was not found.")
    
    # Load the Excel workbook from the template
    wb = openpyxl.load_workbook(template_path)
    
    # Fill the dates in the mini-tables
    month_start_points = [7, 60, 113, 167, 220, 273]  # Starting rows for each mini table
    fill_dates_in_template(wb, week_dates[0], month_start_points)

    # Fill employees in the template
    fill_employees_in_template(wb, schedule_data, week_dates)

    # Save the modified workbook to an in-memory stream (BytesIO)
    from io import BytesIO
    excel_file = BytesIO()
    wb.save(excel_file)
    excel_file.seek(0)

    return excel_file




@login_required
def download_schedule(request):
    month_str = request.GET.get('month')
    if month_str:
        start_date = datetime.strptime(month_str, '%Y-%m-%d').date()
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
    month_str = request.GET.get('month')
    if month_str:
        start_date = datetime.strptime(month_str, '%Y-%m-%d').date()
    else:
        start_date = date.today().replace(day=1)
    
    current_year = start_date.year
    current_month = start_date.month
    days_in_month = monthrange(current_year, current_month)[1]
    
    employees = Employee.objects.all().order_by('group')
    
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    
    # Main timesheet worksheet
    timesheet_worksheet = workbook.add_worksheet('Šihterica')
    
    # Format setup
    formats = setup_formats(workbook)
    timesheet_formats = setup_timesheet_formats(workbook)  # Separate format for timesheet
    
    write_headers(timesheet_worksheet, current_month, current_year, days_in_month, timesheet_formats)
    
    # Process employee data and fill timesheet
    fill_timesheet(timesheet_worksheet, employees, current_year, current_month, days_in_month, timesheet_formats)

    # Generate aggregate tables in separate sheets
    overview_worksheet = workbook.add_worksheet('Pregled svih sati')
    generate_total_overview(overview_worksheet, employees, current_year, current_month, formats)
    
    preparation_worksheet = workbook.add_worksheet('Sati pripreme')
    generate_preparation_hours(preparation_worksheet, employees, current_year, current_month, formats)
    
    excess_worksheet = workbook.add_worksheet('Evidencija viška-manjka sati')
    generate_excess_hours(excess_worksheet, employees, current_year, current_month, formats)
    
    vacation_worksheet = workbook.add_worksheet('Evidencija godišnjih odmora')
    generate_vacation_hours(vacation_worksheet, employees, current_year, current_month, formats)
    
    overtime_worksheet = workbook.add_worksheet('Evidencija prekovremenih sati')
    generate_overtime_hours(overtime_worksheet, employees, current_year, current_month, formats)
    
    workbook.close()
    output.seek(0)

    response = HttpResponse(content=output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="sihterica_{current_month}_{current_year}.xlsx"'
    return response

def setup_formats(workbook):
    """Setup cell formats for the workbook."""
    common_format = {'align': 'center', 'valign': 'vcenter', 'font_size': 12, 'text_wrap': True, 'border': 1}
    formats = {
        'title_format': workbook.add_format({**common_format, 'bold': True, 'font_size': 16}),
        'bold_format': workbook.add_format({**common_format, 'bold': True}),
        'header_format': workbook.add_format({**common_format, 'bold': True, 'bg_color': '#f0f0f0'}),
        'total_format': workbook.add_format({**common_format, 'bg_color': '#d9e1f2'}),
        'hours_format': workbook.add_format({**common_format}),
        'saturday_format': workbook.add_format({**common_format, 'bg_color': '#CCFFCC'}),  # Green
        'sunday_format': workbook.add_format({**common_format, 'bg_color': '#FFFF99'}),  # Yellow
        'gray_format': workbook.add_format({**common_format, 'bg_color': '#E0E0E0'}),  # Gray
        'white_format': workbook.add_format({**common_format, 'bg_color': '#FFFFFF'}),  # White
        'vacation_format': workbook.add_format({**common_format, 'font_color': '#00FF00'}),
        'total_vacation_format': workbook.add_format({**common_format, 'font_color': '#00FF00', 'bg_color': '#d9e1f2'})
    }
    # Group text color formats
    formats['group_text_formats'] = {
        '1': workbook.add_format({**common_format, 'color': '#1E8449', 'bold': True}),
        '2': workbook.add_format({**common_format, 'color': '#D35400', 'bold': True}),
        '3': workbook.add_format({**common_format, 'color': '#2980B9', 'bold': True}),
    }
    return formats

def setup_timesheet_formats(workbook):
    """Setup cell formats specifically for the timesheet."""
    formats = {
        'title_format': workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_size': 16}),
        'bold_format': workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_size': 12}),
        'header_format': workbook.add_format({'align': 'center', 'bold': True, 'bg_color': '#f0f0f0'}),
        'total_format': workbook.add_format({'align': 'center', 'bg_color': '#d9e1f2'}),
        'hours_format': workbook.add_format({'align': 'center'}),
        'saturday_format': workbook.add_format({'align': 'center', 'bg_color': '#CCFFCC'}),  # Green
        'sunday_format': workbook.add_format({'align': 'center', 'bg_color': '#FFFF99'}),  # Yellow
        'gray_format': workbook.add_format({'bg_color': '#E0E0E0', 'align': 'center'}),  # Gray
        'white_format': workbook.add_format({'bg_color': '#FFFFFF', 'align': 'center'}),  # White
        'vacation_format': workbook.add_format({'align': 'center', 'font_color': '#00FF00'}),
        'total_vacation_format': workbook.add_format({'align': 'center','font_color': '#00FF00', 'bg_color': '#d9e1f2'})
    }
    # Group text color formats
    formats['group_text_formats'] = {
        '1': workbook.add_format({'color': '#9C7C14', 'align': 'center', 'valign': 'vcenter', 'font_size': 12, 'bold': True}),
        '2': workbook.add_format({'color': '#c9242d', 'align': 'center', 'valign': 'vcenter', 'font_size': 12, 'bold': True}),
        '3': workbook.add_format({'color': '#118f37', 'align': 'center', 'valign': 'vcenter', 'font_size': 12, 'bold': True}),
        '4': workbook.add_format({'color': '#16448a', 'align': 'center', 'valign': 'vcenter', 'font_size': 12, 'bold': True}),
        '5': workbook.add_format({'color': '#000000', 'align': 'center', 'valign': 'vcenter', 'font_size': 12, 'bold': True}),
        '6': workbook.add_format({'color': '#6b157a', 'align': 'center', 'valign': 'vcenter', 'font_size': 12, 'bold': True}),
    }
    return formats

def write_headers(worksheet, current_month, current_year, days_in_month, formats):
    """Write headers for the worksheet based on current month and year."""
    croatian_months = {
        1: 'Siječanj', 2: 'Veljača', 3: 'Ožujak', 4: 'Travanj', 5: 'Svibanj', 6: 'Lipanj',
        7: 'Srpanj', 8: 'Kolovoz', 9: 'Rujan', 10: 'Listopad', 11: 'Studeni', 12: 'Prosinac'
    }
    month_name = croatian_months[current_month]
    title = f"Evidencija prisutnosti na radu za mjesec {month_name} {current_year}"
    worksheet.merge_range(0, 0, 0, 43, title, formats['title_format'])

    # Set column widths
    worksheet.set_column(0, 0, 20)  # Employee names
    worksheet.set_column(1, 1, 3)    # RD/RN column
    worksheet.set_column(2, 33, 4)   # Day columns
    worksheet.set_column(34, 43, 15) # Aggregate columns

    # Add headers for days and aggregates
    worksheet.merge_range(1, 0, 2, 0, 'Prezime i ime', formats['header_format'])
    day_abbreviations = ['P', 'U', 'S', 'Č', 'P', 'S', 'N']
    for day in range(1, days_in_month + 1):
        weekday = date(year=current_year, month=current_month, day=day).weekday()
        format_to_use = formats['saturday_format'] if weekday == 5 else formats['sunday_format'] if weekday == 6 else formats['header_format']
        worksheet.write(1, day + 1, day_abbreviations[weekday], format_to_use)
        worksheet.write(2, day + 1, str(day), format_to_use)

    # Aggregates headers
    aggregates = ['Fond sati', 'Regularni rad', 'Turnus', 'Višak fonda', 'Subota', 'Nedjelja', 'Noćni rad', 'Blagdan', 'Bolovanje', 'Godišnji odmor']
    for idx, name in enumerate(aggregates, start=34):
        worksheet.merge_range(1, idx, 2, idx, name, formats['total_format'])

def fill_timesheet(worksheet, employees, current_year, current_month, days_in_month, formats):
    row_idx = 3
    for employee in employees:
        group_format = formats['group_text_formats'].get(employee.group, formats['bold_format'])
        worksheet.merge_range(row_idx, 0, row_idx + 1, 0, f"{employee.name} {employee.surname}", group_format)
        worksheet.write(row_idx, 1, 'RD', formats['bold_format'])
        worksheet.write(row_idx + 1, 1, 'RN', formats['bold_format'])

        # Initialize aggregates
        total_day_hours = total_night_hours = total_saturday_hours = 0
        total_sunday_hours = total_holiday_hours = total_sick_leave_hours = 0
        total_vacation_hours = WorkDay.objects.filter(employee=employee, vacation_hours__gt=0).aggregate(Sum('vacation_hours'))['vacation_hours__sum'] or 0

        # Iterate over each day of the month
        for day in range(1, days_in_month + 1):
            current_date = date(year=current_year, month=current_month, day=day)
            work_days = WorkDay.objects.filter(employee=employee, date=current_date)  # Fetch all workdays for the date
            weekday = current_date.weekday()
            base_cell_format = formats['saturday_format'] if weekday == 5 else formats['sunday_format'] if weekday == 6 else formats['hours_format']

            if work_days.exists():
                total_day_hours_for_day = sum(work_day.day_hours for work_day in work_days)
                total_night_hours_for_day = sum(work_day.night_hours for work_day in work_days)
                total_vacation_hours_for_day = sum(work_day.vacation_hours for work_day in work_days)

                day_hours_display = total_day_hours_for_day if total_day_hours_for_day != 0 else ''
                night_hours_display = total_night_hours_for_day if total_night_hours_for_day != 0 else ''

                # Apply green text for vacation only on the 'RD' row and maintain weekend formatting
                if total_vacation_hours_for_day > 0:
                    worksheet.write(row_idx, day + 1, '0', formats['vacation_format'])  # Green zero for RD row
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
        worksheet.merge_range(row_idx, 34, row_idx + 1, 34, hour_fund, formats['total_format'])
        worksheet.merge_range(row_idx, 35, row_idx + 1, 35, redovan_rad, formats['total_format'])
        worksheet.merge_range(row_idx, 36, row_idx + 1, 36, turnus, formats['total_format'])
        worksheet.merge_range(row_idx, 37, row_idx + 1, 37, visak_sati, formats['total_format'])
        worksheet.merge_range(row_idx, 38, row_idx + 1, 38, total_saturday_hours, formats['total_format'])
        worksheet.merge_range(row_idx, 39, row_idx + 1, 39, total_sunday_hours, formats['total_format'])
        worksheet.merge_range(row_idx, 40, row_idx + 1, 40, total_night_hours, formats['total_format'])
        worksheet.merge_range(row_idx, 41, row_idx + 1, 41, total_holiday_hours, formats['total_format'])
        worksheet.merge_range(row_idx, 42, row_idx + 1, 42, total_sick_leave_hours, formats['total_format'])
        worksheet.merge_range(row_idx, 43, row_idx + 1, 43, total_vacation_hours, formats['total_vacation_format'])

        row_idx += 2

def generate_total_overview(worksheet, employees, current_year, current_month, formats):
    row_idx = 0  # Start at the top of the new worksheet
    agg_start_col = 0  # Start at the first column
    
    worksheet.set_column(0, 0, 30)  # Employee name column
    worksheet.set_column(1, 1, 5)   # rb. column
    worksheet.set_column(2, 2, 12)  # Fond sati column
    worksheet.set_column(3, 15, 15)
    
    croatian_months = {
        1: 'Siječanj', 2: 'Veljača', 3: 'Ožujak', 4: 'Travanj', 5: 'Svibanj', 6: 'Lipanj',
        7: 'Srpanj', 8: 'Kolovoz', 9: 'Rujan', 10: 'Listopad', 11: 'Studeni', 12: 'Prosinac'
    }
    month_name = croatian_months[current_month]
    
    # Title for the first aggregate table
    worksheet.merge_range(row_idx, agg_start_col, row_idx, agg_start_col + 15, f'Ukupni sati za {month_name} {current_year}', formats['title_format'])
    row_idx += 1

    # Add first aggregate table headers
    aggregate_headers = ['Ime i Prezime', 'rb.', 'Fond sati', 'Red. rad', 'Drž. pr. i bla.', 'Godišnji o.', 'Bolovanje', 'Noćni rad',
                         'Rad sub.', 'Rad. ned.', 'Slobodan dan', 'Turnus', 'Priprema', 'Prek.rad', 'Prek. USLUGA', 'Prek. Višak Fonda']

    for i, header in enumerate(aggregate_headers):
        worksheet.merge_range(row_idx, agg_start_col + i, row_idx + 1, agg_start_col + i, header, formats['header_format'])

    row_idx += 2

    # Add first aggregate data
    for idx, employee in enumerate(employees):
        work_days = WorkDay.objects.filter(employee=employee, date__year=current_year, date__month=current_month)
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

        # Calculate hour_fund for each employee
        try:
            hour_fund = FixedHourFund.objects.get(month__year=current_year, month__month=current_month).required_hours
        except FixedHourFund.DoesNotExist:
            hour_fund = 168  # Default or error handling scenario

        row_format = formats['gray_format'] if idx % 2 == 0 else formats['white_format']
        
        for col, value in enumerate([f"{employee.name} {employee.surname}", idx + 1, hour_fund, total_day_hours, total_holiday_hours, 
                                     total_vacation_hours, total_sick_leave_hours, total_night_hours, total_saturday_hours, total_sunday_hours, 
                                     total_free_days_hours, total_day_hours + total_night_hours, total_on_call_hours, total_overtime_hours, 0, 0]):
            worksheet.write(row_idx, agg_start_col + col, value, row_format)

        row_idx += 1

    # Add "Ukupno" row for the first aggregate table
    first_data_row = row_idx - len(employees)
    worksheet.write(row_idx, agg_start_col, 'Ukupno', formats['header_format'])

    for col_num in range(2, 16):
        column_letter_value = column_letter(col_num + 1)
        formula_range = f"{column_letter_value}{first_data_row}:{column_letter_value}{row_idx}"
        worksheet.write_formula(row_idx, col_num, f"=SUM({formula_range})", formats['total_format'])

def generate_preparation_hours(worksheet, employees, current_year, current_month, formats):
    worksheet.set_column(0, 0, 30)  # Employee name column
    worksheet.set_column(1, 1, 5)   # rb. column
    worksheet.set_column(2, 6, 10)  # Week columns
    worksheet.set_column(7, 7, 20)  # Priprema um. prekovremene column
    worksheet.set_column(8, 8, 12) # Ukupno column

    first_day_of_month = date(current_year, current_month, 1)
    last_day_of_month = date(current_year, current_month, monthrange(current_year, current_month)[1])
    weeks = {((first_day_of_month + timedelta(days=x)).isocalendar()[1]) for x in range((last_day_of_month - first_day_of_month).days + 1)}

    agg_start_row = 0
    worksheet.merge_range(agg_start_row, 0, agg_start_row, 8, 'BROJ SATI PRIPREME', formats['title_format'])
    agg_start_row += 1

    worksheet.write(agg_start_row, 0, 'Ime i Prezime', formats['header_format'])
    worksheet.write(agg_start_row, 1, 'rb.', formats['header_format'])
    
    start_week_col = 2
    end_week_col = start_week_col + len(weeks) - 1
    worksheet.merge_range(agg_start_row, start_week_col, agg_start_row, end_week_col, 'Prip. iz rasporeda', formats['header_format'])
    worksheet.write(agg_start_row, end_week_col + 1, 'Priprema um. prekovremene', formats['header_format'])
    worksheet.write(agg_start_row, end_week_col + 2, 'Ukupno', formats['header_format'])
    
    agg_start_row += 1
    
    for idx, employee in enumerate(employees):
        row_format = formats['gray_format'] if idx % 2 == 0 else formats['white_format']
        worksheet.write(agg_start_row, 0, f"{employee.name} {employee.surname}", row_format)
        worksheet.write(agg_start_row, 1, idx + 1, row_format)
        
        col_offset = 2
        total_weekly_hours = 0
        for week_num in sorted(weeks):
            week_days = [first_day_of_month + timedelta(days=x) for x in range((last_day_of_month - first_day_of_month).days + 1) if (first_day_of_month + timedelta(days=x)).isocalendar()[1] == week_num]
            weekly_hours = sum(WorkDay.objects.filter(employee=employee, date__in=week_days).values_list('on_call_hours', flat=True))
            worksheet.write(agg_start_row, col_offset, weekly_hours, row_format)
            total_weekly_hours += weekly_hours
            col_offset += 1
        
        worksheet.write(agg_start_row, col_offset, 0, row_format)
        worksheet.write(agg_start_row, col_offset + 1, total_weekly_hours, row_format)
        
        agg_start_row += 1

def generate_excess_hours(worksheet, employees, current_year, current_month, formats):
    worksheet.set_column(0, 0, 30)  # Employee name column
    worksheet.set_column(1, 1, 5)
    worksheet.set_column(2, 4, 20)
    
    agg_start_row = 0
    worksheet.merge_range(agg_start_row, 0, agg_start_row, 4, 'EVIDENCIJA VIŠKA-MANJKA SATI', formats['title_format'])
    sub_headers = ['PREZIME I IME', 'rb', f"Fond sati s {monthrange(current_year, current_month - 1 if current_month > 1 else 12)[1]}.{current_month - 1 if current_month > 1 else 12}", f"Višak fonda ({current_month} {current_year})", f"Fond sati s {monthrange(current_year, current_month)[1]}.{current_month}"]
    
    for i, header in enumerate(sub_headers):
        worksheet.merge_range(agg_start_row + 1, i, agg_start_row + 2, i, header, formats['header_format'])
    agg_start_row += 3

    for idx, employee in enumerate(employees):
        try:
            previous_excess_record = ExcessHours.objects.get(employee=employee, year=current_year if current_month > 1 else current_year - 1, month=current_month - 1 if current_month > 1 else 12)
            previous_excess = previous_excess_record.excess_hours
        except ExcessHours.DoesNotExist:
            previous_excess = 0

        current_excess = employee.calculate_visak_sati(current_month, current_year)
        cumulative_excess_current_month = previous_excess + current_excess

        row_format = formats['gray_format'] if idx % 2 == 0 else formats['white_format']

        worksheet.write(agg_start_row, 0, f"{employee.surname} {employee.name}", row_format)
        worksheet.write(agg_start_row, 1, idx + 1, row_format)
        worksheet.write(agg_start_row, 2, previous_excess, formats['hours_format'])
        worksheet.write(agg_start_row, 3, current_excess, formats['hours_format'])
        worksheet.write(agg_start_row, 4, cumulative_excess_current_month, formats['hours_format'])

        agg_start_row += 1

def generate_vacation_hours(worksheet, employees, current_year, current_month, formats):
    worksheet.set_column(0, 0, 30)  # Employee name column
    worksheet.set_column(1, 4, 15)
    
    agg_vacation_start_row = 0
    worksheet.merge_range(agg_vacation_start_row, 0, agg_vacation_start_row, 4, 'EVIDENCIJA GODIŠNJIH ODMORA', formats['title_format'])
    vacation_headers = ['Prezime i ime', f"GO s {monthrange(current_year, current_month - 1 if current_month > 1 else 12)[1]}.{current_month - 1 if current_month > 1 else 12}.{current_year if current_month > 1 else current_year - 1}", f"GO sati ({current_month}.{current_year})", f"GO dani ({current_month}.{current_year})", f"GO s {monthrange(current_year, current_month)[1]}.{current_month}"]

    for i, header in enumerate(vacation_headers):
        worksheet.merge_range(agg_vacation_start_row + 1, i, agg_vacation_start_row + 2, i, header, formats['header_format'])
    agg_vacation_start_row += 3

    for idx, employee in enumerate(employees):
        previous_vacation_record = ExcessHours.objects.filter(employee=employee, year=current_year if current_month > 1 else current_year - 1, month=current_month - 1 if current_month > 1 else 12).first()
        previous_vacation_hours = previous_vacation_record.vacation_hours_used if previous_vacation_record else 0

        current_vacation_hours = WorkDay.objects.filter(employee=employee, date__year=current_year, date__month=current_month).aggregate(Sum('vacation_hours'))['vacation_hours__sum'] or 0
        current_vacation_days = current_vacation_hours / 8

        new_cumulative_vacation_hours = previous_vacation_hours + current_vacation_hours
        new_cumulative_vacation_days = new_cumulative_vacation_hours / 8

        row_format = formats['gray_format'] if idx % 2 == 0 else formats['white_format']

        worksheet.write(agg_vacation_start_row, 0, f"{employee.surname} {employee.name}", row_format)
        worksheet.write(agg_vacation_start_row, 1, previous_vacation_hours / 8, formats['hours_format'])
        worksheet.write(agg_vacation_start_row, 2, current_vacation_hours, formats['hours_format'])
        worksheet.write(agg_vacation_start_row, 3, current_vacation_days, formats['hours_format'])
        worksheet.write(agg_vacation_start_row, 4, new_cumulative_vacation_days, formats['hours_format'])

        agg_vacation_start_row += 1

def sum_decimal_hours(decimal_hours):
    """Sums a list of decimal hours, converting minute values correctly."""
    total_hours = 0
    total_minutes = 0
    for decimal in decimal_hours:
        hours = int(decimal)
        minutes = (decimal - hours) * 100
        total_hours += hours
        total_minutes += minutes

    # Convert total minutes to hours and minutes
    total_hours += total_minutes // 60
    total_minutes = total_minutes % 60

    return total_hours + total_minutes / 100.0

def generate_overtime_hours(worksheet, employees, current_year, current_month, formats):
    worksheet.set_column(0, 0, 30)  # Employee name column
    worksheet.set_column(1, 1, 5)
    worksheet.set_column(2, 8, 20)
    agg_overtime_start_row = 0

    overtime_headers = [
        'Prezime i ime', 'rb', 'Prek. pripreme', 'Prek. USLUGA priprema', 
        'Prek. višak fonda', 'Prekovremeno slobodan dan', 
        'Prekovremeno slobodan dan usluga', 'Ukupno prek.', 'Ukupno prek. USLUGA'
    ]
    worksheet.merge_range(
        agg_overtime_start_row, 0, agg_overtime_start_row, 
        9, 'EVIDENCIJA PREKOVREMENIH SATI', formats['title_format']
    )
    for i, header in enumerate(overtime_headers):
        worksheet.merge_range(agg_overtime_start_row + 1, i, agg_overtime_start_row + 2, i, header, formats['header_format'])
    agg_overtime_start_row += 3

    for idx, employee in enumerate(employees):
        work_days = WorkDay.objects.filter(employee=employee, date__year=current_year, date__month=current_month)
        
        total_overtime_preparation = sum_decimal_hours([day.overtime_hours for day in work_days])
        total_overtime_service = sum_decimal_hours([day.overtime_service for day in work_days])
        total_overtime_excess_fond = sum_decimal_hours([day.overtime_excess_fond for day in work_days])
        total_overtime_free_day = sum_decimal_hours([day.overtime_free_day for day in work_days])
        total_overtime_free_day_service = sum_decimal_hours([day.overtime_free_day_service for day in work_days])

        total_overtime = total_overtime_preparation + total_overtime_service + total_overtime_excess_fond
        total_overtime_service_total = total_overtime_free_day + total_overtime_free_day_service

        row_format = formats['gray_format'] if idx % 2 == 0 else formats['white_format']

        worksheet.write(agg_overtime_start_row, 0, f"{employee.surname} {employee.name}", row_format)
        worksheet.write(agg_overtime_start_row, 1, idx + 1, row_format)
        worksheet.write(agg_overtime_start_row, 2, total_overtime_preparation, formats['hours_format'])
        worksheet.write(agg_overtime_start_row, 3, total_overtime_service, formats['hours_format'])
        worksheet.write(agg_overtime_start_row, 4, total_overtime_excess_fond, formats['hours_format'])
        worksheet.write(agg_overtime_start_row, 5, total_overtime_free_day, formats['hours_format'])
        worksheet.write(agg_overtime_start_row, 6, total_overtime_free_day_service, formats['hours_format'])
        worksheet.write(agg_overtime_start_row, 7, total_overtime, formats['hours_format'])
        worksheet.write(agg_overtime_start_row, 8, total_overtime_service_total, formats['hours_format'])

        agg_overtime_start_row += 1

    first_overtime_data_row = agg_overtime_start_row - len(employees)
    worksheet.write(agg_overtime_start_row, 0, 'Ukupno', formats['header_format'])

    for col_offset in range(2, 9):
        column_letter_value = column_letter(34 + col_offset)
        formula_range = f"{column_letter_value}{first_overtime_data_row + 1}:{column_letter_value}{agg_overtime_start_row}"
        worksheet.write_formula(agg_overtime_start_row, col_offset, f"=SUM({formula_range})", formats['total_format'])

def column_letter(index):
    index -= 1
    result = ''
    while index >= 0:
        result = chr(index % 26 + 65) + result
        index = index // 26 - 1
    return result
