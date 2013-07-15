from charmhelpers.core.host import (
    apt_install,
    filter_installed_packages
)


TEMPLATES_DIR = 'templates'

try:
    import jinja2
except ImportError:
    apt_install(filter_installed_packages(['python-jinja2']),
                fatal=True)
    import jinja2


def render_template(template_name, context, template_dir=TEMPLATES_DIR):
    templates = jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_dir))
    template = templates.get_template(template_name)
    return template.render(context)



def plop():
    import charmhelpers.core.hookenv as hookenv
    hookenv.log("PLOP PLOP PLOP")
