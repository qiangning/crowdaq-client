#!/usr/bin/env python3
import json
import sys
from os.path import expanduser

import click
import requests
import os
import getpass
import logging
from datetime import datetime

from client import Client, resolve_resource, resolve_resource_with_name


def load_config(config_file):
    conf = {
        "endpoint": "",
        "user": "",
        "password": "",
        "defaultKey": "",
        "token": "",
    }

    if os.path.isfile(config_file):
        with open(config_file) as config_input:
            conf = json.load(config_input)
            return conf
    else:
        raise ValueError(f"{config_file} is not a file.")


def cache_token(token, config, config_file):
    config['token'] = token
    with open(config_file, "w") as of:
        json.dump(config, of, indent=4)


@click.group()
@click.option("--config-file", '-c', default="~/.crowdaq/config.json")
@click.option("--debug", is_flag=True)
@click.pass_context
def cli(ctx, config_file, debug):
    if debug:
        logging.basicConfig(level=logging.DEBUG)

    ctx.ensure_object(dict)
    ctx.obj['config_filepath'] = expanduser(config_file)


@cli.command()
@click.pass_context
def config(ctx):
    click.echo('Configure your client')
    config_filepath = ctx.obj['config_filepath']

    conf = {
        "site_url": "",
        "user": "",
        "password": "",
        "token": "",
    }

    if os.path.isfile(config_filepath):
        with open(config_filepath) as config_input:
            conf = json.load(config_input)

    new_conf = {}

    site_url = input(f"What's your site_url url? ({conf['site_url']}) ").strip().rstrip('/')
    new_conf['site_url'] = site_url if len(site_url) > 0 else conf['site_url']

    username = input(f"What's your username? ({conf['user']}) ").strip()
    new_conf['user'] = username if len(username) > 0 else conf['user']

    print("Input your password")
    password = getpass.getpass().strip()
    new_conf['password'] = password if len(password) > 0 else conf['password']

    new_conf['token'] = ""

    config_dir = os.path.dirname(config_filepath)
    if config_dir and not os.path.exists(config_dir):
        os.makedirs(config_dir)
    with open(config_filepath, "w") as config_out:
        json.dump(new_conf, config_out, indent=4)


@cli.command('login')
@click.pass_context
def _login(ctx):
    conf = load_config(ctx.obj['config_filepath'])

    url = f"{conf['site_url']}/api/login"
    resp = requests.post(url, params={
        "username": conf['user'],
        "password": conf['password'],
    })

    logging.debug(f"resp.status_code={resp.status_code}")
    logging.debug(f"Response={resp.content.decode('utf-8')}")

    o = json.loads(resp.content.decode('utf-8'))
    cache_token(token=o['token'], config=conf, config_file=ctx.obj['config_filepath'])



@cli.command("get-token")
@click.pass_context
def _get_token(ctx):
    conf = load_config(ctx.obj['config_filepath'])

    url = f"{conf['site_url']}/api/login"
    resp = requests.post(url, params={
        "username": conf['user'],
        "password": conf['password'],
    })

    o = json.loads(resp.content.decode('utf-8'))
    cache_token(token=o['token'], config=conf, config_file=ctx.obj['config_filepath'])
    print(o['token'])


@cli.command("create")
@click.argument('resource')
@click.argument('file')
@click.option('--overwrite/--no-overwrite', '-o/ ', default=False)
@click.pass_context
def _create(ctx, resource: str, file: str, overwrite):
    conf = load_config(ctx.obj['config_filepath'])
    client = Client(conf)

    resources, resource_type, resource_id = resolve_resource_with_name(resource, client)
    resource_def = ""
    with open(file) as file_input:
        resource_def = file_input.read()

    if resource_type == "instruction":
        if file.endswith(".md"):
            resource_def = json.dumps(
                {
                    "document": resource_def
                }
            )
        elif file.endswith(".json"):
            pass
        else:
            raise ValueError("Instruction definition file must ends with either md or json")

    # Should validate resource schema here.
    if overwrite or resources.get(resource_id) is None:
        resources.update(resource_id, resource_def)
    else:
        print("Resource already exists.")


@cli.command("get")
@click.argument('resource')
@click.pass_context
def _get(ctx, resource):
    conf = load_config(ctx.obj['config_filepath'])
    client = Client(conf)
    print(f"Found the following resource under {resource}")
    resources, resource_type, resource_id = resolve_resource_with_name(resource, client)
    print(resources.get(resource_id))


@cli.command("list")
@click.argument('resource')
@click.pass_context
def _list(ctx, resource):
    conf = load_config(ctx.obj['config_filepath'])
    client = Client(conf)
    print(f"Found the following resource under {resource}")
    resource, resource_type = resolve_resource(resource, client)
    for item in resource.list():
        print(f"{item['name']}")


@cli.command("set")
@click.argument('resource')
@click.argument('modifiers')
@click.pass_context
def _set(ctx, resource, modifiers):
    conf = load_config(ctx.obj['config_filepath'])
    client = Client(conf)
    print(f"Found the following resource under {resource}")
    resources, resource_type, resource_id = resolve_resource_with_name(resource, client)

    if resource_type != "question":
        print(f"Set is not available for the resource type: {resource_type}")
        sys.exit(1)

    modifiers = modifiers.split(",")
    params = {}

    for modifier in modifiers:
        k, v = modifier.split("=")
        params[k] = v


@cli.command("sync-response")
@click.argument('resource')
@click.argument('output_folder')
@click.pass_context
def _sync_response(ctx, resource, output_folder):
    conf = load_config(ctx.obj['config_filepath'])
    client = Client(conf)
    print(f"Found the following resource under {resource}")
    resources, resource_type, resource_id = resolve_resource_with_name(resource, client)

    if resource_type != "exam":
        print(f"Sync response is not available for the resource type: {resource_type}")
        sys.exit(1)


    loaded_pids = set()

    print("Loading existing files now.")
    for f in os.listdir(output_folder):
        if f.startswith("crowdaq_assignment_sync_") and f.endswith(".json"):
            fullpath = os.path.join(output_folder, f)
            with open(fullpath) as input_fd:
                try:
                    records = json.load(input_fd)
                except json.decoder.JSONDecodeError as e:
                    print(f"File {f} cannot be loaded.")
                    continue
                for r in records:
                    loaded_pids.add(r['pid'])

    print(f"Found {len(loaded_pids)} records downloaded.")
    response_ids = resources.list_responses(resource_id)
    print(f"Server has total {len(response_ids)} responses.")

    pids_to_load = {x for x in response_ids['results']}.difference(loaded_pids)
    print(f"{len(pids_to_load)} records will be downloaded now.")
    if len(pids_to_load) == 0:
        return

    all_responses = resources.get_responses(resource_id, pids_to_load)
    now = datetime.now()
    dt_string = now.strftime("%Y-%m-%d-%H-%M-%S")
    output_filename = os.path.join(output_folder, f"crowdaq_assignment_sync_{dt_string}.json")
    with open(output_filename, "w") as output_fd:
        json.dump(all_responses['results'], output_fd, indent=2)

    print("Finished.")


@cli.command("get-report")
@click.argument('resource')
@click.pass_context
def _get_report(ctx, resource):
    conf = load_config(ctx.obj['config_filepath'])
    client = Client(conf)
    print(f"Found the following resource under {resource}")
    resources, resource_type, resource_id = resolve_resource_with_name(resource, client)

    if resource_type != "exam":
        print(f"get-report is not available for the resource type: {resource_type}")
        sys.exit(1)

    report = resources.get_report(resource_id)
    print(report)


@cli.command("post")
@click.argument('url')
@click.option('--body', "-b")
@click.pass_context
def post(ctx, url, body):
    conf = load_config(ctx.obj['config_filepath'])
    client = Client(conf)

    if body is not None:
        with open(body) as input_fd:
            resp = requests.post(url, input_fd.read(), headers=client.auth_headers)
    else:
        resp = requests.post(url, headers=client.auth_headers)
    print(resp.status_code)
    print(resp.content.decode('utf-8'))


@cli.command("get")
@click.argument('url')
@click.pass_context
def get(ctx, url):
    conf = load_config(ctx.obj['config_filepath'])
    client = Client(conf)
    resp = requests.get(url, headers=client.auth_headers)
    print(resp.status_code, file=sys.stderr)
    print(resp.content.decode('utf-8'))

@cli.command("gen-unfinished-urls")
@click.argument('taskname')
@click.argument('targetcnt',type=int)
@click.pass_context
def gen_task_unfinished_urls(ctx, taskname, targetcnt):
    conf = load_config(ctx.obj['config_filepath'])
    client = Client(conf)
    url = f"{conf['site_url']}/api/task_report/{conf['user']}/{taskname}"
    resp = requests.get(url, headers=client.auth_headers)
    print(resp.status_code, file=sys.stderr)
    progress = json.loads(resp.content.decode('utf-8'))
    for p in progress['assignment_count']:
        taskid = p['task_id']
        count = p['count']
        for _ in range(count,targetcnt):
            print(f"{conf['site_url']}/w/task/{conf['user']}/{taskname}/{taskid}")


if __name__ == '__main__':
    cli()
