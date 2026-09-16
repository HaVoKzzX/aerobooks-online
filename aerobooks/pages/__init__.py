from aerobooks.pages import (
    admin,
    dashboard,
    earnings,
    expenses,
    hours,
    invoices,
    login,
    request_access,
    settings,
    students,
    team,
)


def register() -> None:
    login.register()
    request_access.register()
    admin.register()
    team.register()
    dashboard.register()
    students.register()
    hours.register()
    invoices.register()
    expenses.register()
    earnings.register()
    settings.register()
