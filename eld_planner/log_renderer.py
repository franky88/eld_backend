def render_logs(days: list) -> list:
    """
    Validate and clean log data from the HOS engine before
    sending to the frontend. Ensures totals sum to 24.0 and
    events are properly ordered.
    """
    output = []
    for day in days:
        events = day['events']

        # Sort events by start_hour
        events = sorted(events, key=lambda e: e['start_hour'])

        # Validate totals sum to 24.0
        totals = day['totals']
        total_sum = sum(totals.values())
        if abs(total_sum - 24.0) > 0.01:
            diff = 24.0 - total_sum
            totals['offDuty'] = round(totals['offDuty'] + diff, 2)

        output.append({
            'day': day['day'],
            'fields': day['fields'],
            'events': events,
            'remarks': day['remarks'],
            'totals': totals,
        })

    return output