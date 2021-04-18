from os import listdir, walk
from os.path import join, exists
from re import match, MULTILINE
from json import dumps
import string
from subprocess import Popen, PIPE, check_output
from flask import Flask, request, Request, abort, send_file, jsonify, render_template

root_dir = "F:\\Steam\\steamapps\\common\\rFactor 2\\"


def get_steam_workshop_item_list(root_dir):
    steam_packages_path = root_dir.replace(
        "common\\rFactor 2", "workshop\\content\\365960"
    )
    workshop_items = {}
    for workshop_id in listdir(steam_packages_path):
        workshop_item_root = join(steam_packages_path, workshop_id)
        items = listdir(workshop_item_root)
        workshop_items[workshop_id] = items
    return workshop_items


def get_component_tree(root_dir):
    installed_folder = join(root_dir, "Installed")
    component_types = listdir(installed_folder)
    manifest_needles = ["Name", "Version", "Signature", "BaseSignature"]
    component_tree = {}
    component_hashmap = []
    steam_items = get_steam_workshop_item_list(root_dir)
    packages_items = listdir(join(root_dir, "Packages"))
    usages = get_usages(root_dir)
    for r, d, f in walk(installed_folder):
        for file in f:
            if ".mft" in file:
                full_path = join(r, file)
                manifest_properties = {}
                component_type_raw = r.replace(installed_folder, "").strip("\\")
                component_type_path_types = component_type_raw.split("\\")
                component_type = component_type_path_types[0]
                component_name = component_type_path_types[1]
                if component_type not in component_tree:
                    component_tree[component_type] = []
                with open(full_path, "r") as file:
                    content = file.readlines()
                    if content:
                        props = {}
                        for needle in manifest_needles:
                            pattern = r"" + needle + "=(.+)"
                            for line in content:
                                got = match(pattern, line)
                                if got:
                                    value = got.groups(1)
                                    props[needle] = value[0]
                        props["Children"] = []
                        props["Remarks"] = []
                        props["WorkshopId"] = None
                        props["Folder"] = r.replace(
                            join(installed_folder, component_type, props["Name"])
                            + "\\",
                            "",
                        )
                        props["UsedIn"] = []
                        for manifest, manifest_signatures in usages.items():
                            if props["Signature"] in manifest_signatures:
                                props["UsedIn"].append(manifest)

                        comp_hash = props["Name"] + props["Version"]
                        if comp_hash not in component_hashmap:
                            component_hashmap.append(comp_hash)
                        else:
                            props["Remarks"].append(
                                "The component is a duplicate of {} {}".format(
                                    props["Name"], props["Version"]
                                )
                            )
                        if "(" in props["Folder"]:
                            props["Remarks"].append(
                                "Component folder was an (once) a duplicate"
                            )
                        # identify steam origin, if existing
                        for workshop_id, items in steam_items.items():
                            for item in items:
                                needle_version = props["Version"]
                                if "(" in needle_version:
                                    needle_version = needle_version.split("(")[
                                        0
                                    ].strip()
                                if props["Name"] in item and needle_version in item:
                                    props["WorkshopId"] = workshop_id
                                    break

                        if "Signature" in props:
                            if "BaseSignature" in props:
                                # the component is an update
                                found_base = False
                                for component in component_tree[component_type]:
                                    if component["Signature"] == props["BaseSignature"]:
                                        component["Children"].append(props)
                                        found_base = True
                                        break
                                if not found_base:
                                    props["Remarks"].append(
                                        "Base mod {} not found".format(
                                            props["BaseSignature"][0:10]
                                        )
                                    )
                                    component_tree[component_type].append(props)
                            else:
                                component_tree[component_type].append(props)
    first_level_comps = []
    for component_type, items in component_tree.items():
        for item in items:
            if item["Name"] not in first_level_comps:
                first_level_comps.append(item["Name"])
            else:
                item["Remarks"].append(
                    "Multiple mods with same component but different base version."
                )
    return component_tree


def strings(filename):
    pattern = r"(Name|Version|Type|Signature|BaseSignature)=(.*)"
    results = {}
    try:
        ps = Popen(("strings", filename), stdout=PIPE)
        output = check_output(
            ("grep", "-E", "(Name|Version|Type|Signature|BaseSignature)"),
            stdin=ps.stdout,
        )
        ps.wait()
        raw_matches = output.decode("utf-8").split("\n")
        for raw_match in raw_matches:
            if raw_match:
                got = match(pattern, raw_match)
                if got:
                    name = got.groups(1)[0]
                    value = got.groups(1)[1]
                    results[name] = value
    except Exception as ex:
        print(ex)
        pass
    return results


def identify_components_from_packages(root_dir):
    files = listdir(root_dir)
    components = {}
    for file in files:
        full_path = join(root_dir, file)
        if ".rfcmp" in full_path:
            components[file] = strings(full_path)
    return components


def get_subscriptions(root_dir):
    steam_packages_path = root_dir.replace(
        "common\\rFactor 2", "workshop\\content\\365960"
    )
    workshop_items = {}
    for workshop_id in listdir(steam_packages_path):
        workshop_item_root = join(steam_packages_path, workshop_id)
        items = identify_components_from_packages(workshop_item_root)
        workshop_items[workshop_id] = items
    return workshop_items


def get_usages(root_dir):
    manifests_path = join(root_dir, "Manifests")
    files = listdir(manifests_path)
    manifests = {}
    for manifest in files:
        full_path = join(manifests_path, manifest)
        with open(full_path, "r") as file:
            content = file.readlines()
            result = []
            for line in content:
                matches = match(r"Signature=(.+)", line)
                if matches:
                    result.append(matches.group(1))

            manifests[manifest] = result
    return manifests


# print(dumps(get_component_tree(root_dir)))
# print(identify_components_from_packages(join(root_dir, "Packages")))
# print(dumps(get_subscriptions(root_dir)))

app = Flask(__name__)


@app.route("/packages", methods=["GET"])
def action():
    packages = get_component_tree(root_dir)
    return render_template("packages.html", packages=packages)


app.run(
    host="localhost",
    port="8888",
    debug=True,
)