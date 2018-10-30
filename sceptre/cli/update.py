from uuid import uuid1

import click

from sceptre.context import SceptreContext
from sceptre.cli.helpers import catch_exceptions, confirmation
from sceptre.cli.helpers import write, get_stack_or_stack_group
from sceptre.cli.helpers import simplify_change_set_description
from sceptre.stack_status import StackStatus, StackChangeSetStatus
from sceptre.plan.plan import SceptrePlan


@click.command(name="update")
@click.argument("path")
@click.option(
    "-c", "--change-set", is_flag=True,
    help="Create a change set before updating."
)
@click.option(
    "-v", "--verbose", is_flag=True, help="Display verbose output."
)
@click.option(
    "-y", "--yes", is_flag=True, help="Assume yes to all questions."
)
@click.pass_context
@catch_exceptions
def update_command(ctx, path, change_set, verbose, yes):
    """
    Update a stack.

    Updates a stack for a given config PATH. Or perform an update via
    change-set when the change-set flag is set.
    """
    context = SceptreContext(
                command_path=path,
                project_path=ctx.obj.get("project_path", None),
                user_variables=ctx.obj.get("user_variables", {}),
                options=ctx.obj.get("options", {}),
                output_format=ctx.obj.get("output_format", None)
            )

    stack, _ = get_stack_or_stack_group(context, path)
    if change_set:
        action = 'create_change_set'
        change_set_name = "-".join(["change-set", uuid1().hex])
        plan = SceptrePlan(context, action, stack)
        plan.execute(change_set_name)
        try:
            # Wait for change set to be created
            plan.action = 'wait_for_cs_completion'
            status = plan.execute(change_set_name)

            # Exit if change set fails to create
            if status != StackChangeSetStatus.READY:
                exit(1)

            # Describe changes
            plan.action = 'describe_change_set'
            description = plan.execute(change_set_name)
            if not verbose:
                description = simplify_change_set_description(description)
            write(description, context.output_format)

            # Execute change set if happy with changes
            if yes or click.confirm("Proceed with stack update?"):
                plan.action = 'execute_change_set'
                plan.execute(change_set_name)
        finally:
            # Clean up by deleting change set
            plan.action = 'delete_change_set'
            plan.execute(change_set_name)
    else:
        confirmation("update", yes, stack=path)
        action = 'update'
        plan = SceptrePlan(context, action, stack)
        response = plan.execute()
        if response != StackStatus.COMPLETE:
            exit(1)
