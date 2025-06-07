"Repository rule to generate `py_type_library` from input typings/stubs requirements."

_PY_TYPE_LIBRARY_TEMPLATE = """
py_type_library(
    name = "{typing_requirement}",
    typing = requirement("{typing_requirement}"),
    visibility = ["//visibility:public"],
)
"""

def _render_build(rctx, type_mappings):
    content = ""
    content += """load("{pip_requirements}", "requirement")\n""".format(
        pip_requirements = rctx.attr.pip_requirements,
    )
    content += """load("@rules_mypy//mypy:py_type_library.bzl", "py_type_library")\n"""
    for typing_requirement in type_mappings.values():
        content += _PY_TYPE_LIBRARY_TEMPLATE.format(
            typing_requirement = typing_requirement,
        ) + "\n"
    return content

def _render_types_bzl(rctx, type_mappings):
    content = ""
    content += """load("{pip_requirements}", "requirement")\n""".format(
        pip_requirements = rctx.attr.pip_requirements,
    )
    content += "types = {\n"

    for requirement, typing_requirement in type_mappings.items():
        content += """    requirement("{requirement}"): "@@{name}//:{typing_requirement}",\n""".format(
            requirement = requirement,
            name = str(rctx.attr.name),
            typing_requirement = typing_requirement,
        )
    content += "}\n"
    return content

def _generate_impl(rctx):
    contents = rctx.read(rctx.attr.requirements_txt)

    packages = []
    types = []

    # this is a very, very naive parser
    for line in contents.splitlines():
        if line.startswith("#") or line == "":
            continue

        if ";" in line:
            line, _ = line.split(";")

        if "~=" in line:
            req, _ = line.split("~=")
        elif "==" in line:
            req, _ = line.split("==")
        elif "<=" in line:
            req, _ = line.split("<=")
        else:
            continue

        req = req.strip()
        if req.endswith("-stubs") or req.startswith("types-"):
            types.append((req.removeprefix("types-").removesuffix("-stubs"), req))
        else:
            packages.append(req)

    type_mappings = dict()
    for requirement, typing_requirement in types:
        if requirement not in packages:
            print("warning: missing matching requirement for {}".format(
                typing_requirement,
            ))
        elif requirement in type_mappings:
            print("warning, duplicate typings {} and {} for {}".format(
                type_mappings[requirement],
                typing_requirement,
                requirement,
            ))
        else:
            type_mappings[requirement] = typing_requirement

    rctx.file("BUILD.bazel", content = _render_build(rctx, type_mappings))
    rctx.file("types.bzl", content = _render_types_bzl(rctx, type_mappings))

generate = repository_rule(
    implementation = _generate_impl,
    attrs = {
        "pip_requirements": attr.label(),
        "requirements_txt": attr.label(allow_single_file = True),
    },
)
