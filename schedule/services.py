from collections import defaultdict
from datetime import datetime, timedelta

from django.utils import timezone

from .models import Appointment, WeeklyAvailability


def generate_slots(doctor, start_date, days=7, duration=30):
    """Expand a doctor's weekly windows into fixed-length slots for `days` days."""
    tz = timezone.get_current_timezone()
    now = timezone.now()
    step = timedelta(minutes=duration)

    windows_by_weekday = defaultdict(list)
    for w in WeeklyAvailability.objects.filter(doctor=doctor):
        windows_by_weekday[w.weekday].append(w)

    # Active appointments in this date range, loaded once (INSIDE the function)
    booked = list(
        Appointment.objects.filter(
            doctor=doctor,
            status__in=["pending", "confirmed"],
            start__date__gte=start_date,
            start__date__lte=start_date + timedelta(days=days),
        )
    )

    def is_taken(slot_start, slot_end):
        return any(a.start < slot_end and a.end > slot_start for a in booked)

    result = []
    for offset in range(days):
        day = start_date + timedelta(days=offset)
        slots = []

        for w in windows_by_weekday.get(day.weekday(), []):
            cursor = timezone.make_aware(datetime.combine(day, w.start_time), tz)
            window_end = timezone.make_aware(datetime.combine(day, w.end_time), tz)

            while cursor + step <= window_end:
                if cursor > now and not is_taken(cursor, cursor + step):
                    slots.append({
                        "start": cursor.isoformat(),
                        "end": (cursor + step).isoformat(),
                    })
                cursor += step

        result.append({
            "date": day.isoformat(),
            "weekday": day.weekday(),
            "weekday_name": day.strftime("%A"),
            "slots": slots,
        })
    return result