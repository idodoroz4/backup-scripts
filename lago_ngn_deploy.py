#!/usr/bin/python2.7

import ovirtlago
import lago
import subprocess
import os
import shutil
import time
import json


LCL_REPO_PATH = r'common/deploy-scripts/add_local_repo.sh'
HTTP_SERVER_ADDR = r'192.168.100.1'
HTTP_SERVER_PORT = 8585
SUITE = r"ngn_suite_3.6"
INIT_DST = SUITE + "/init.json.in"
INIT_SRC = "../common/init-configs/ngn_1_centos6_engine_2_centos7_hosts.json"
NGN_FUNC = """run_ngn_suite(){
  env_init "http://templates.ovirt.org/repo/repo.metadata"
  env_repo_setup

}"""

http_server = None
ngn_qcow2_path = ""


# replace the run_suite function call to run_ngn_suite in run_suite.sh
def replace_lines_in_run_suite(
    current_lines = 'run_suite',
    new_lines = 'run_ngn_suite'
    ):

    data = ''
    with open('run_suite.sh', 'r') as myfile:
        data = myfile.read().replace( current_lines, new_lines)

    with open('run_suite.sh', 'w') as myfile:
        myfile.write(data)

# add run_ngn_suite function in $SUITE/control.sh
def add_ngn_function():
    is_function_exist = False
    with open(SUITE + r'/control.sh', 'r') as myfile:
        script_content = myfile.read()
        if "run_ngn_suite()" in script_content:
            is_function_exist = True

    if not is_function_exist :
        with open(SUITE + r'/control.sh', 'a') as myfile:
            myfile.write(NGN_FUNC)

#clone ngn from git
def clone_ngn ():
    if os.path.isdir("ovirt-node-ng"):
        shutil.rmtree("ovirt-node-ng")
    subprocess.call(["git","clone",r"git://gerrit.ovirt.org/ovirt-node-ng.git"])

# change the content of the kickstart file and change the repo.
def change_kickstart_file ():
    # copy lines  add_repo_file
    local_repo_lines = []
    ngn_ks_in_lines = []
    ks_in_path = get_file_full_path("ovirt-node-ng/data","in")
    with open(LCL_REPO_PATH,'r') as local_repo, open(ks_in_path,'r') as ngn_ks_in:
        local_repo_lines = local_repo.readlines()
        ngn_ks_in_lines = ngn_ks_in.readlines()


    #open("ovirt-node-ng-image.ks.in.new",'w').close()

    ngn_ks_in_new = open(ks_in_path,'w')
    replace_lines = True
    for line in ngn_ks_in_lines:
        if "EOR" in line:
            replace_lines = not replace_lines
            if ( not replace_lines):
                for line2 in local_repo_lines:
                    if "baseurl" in line2:
                        line2 = r"baseurl=http://" + HTTP_SERVER_ADDR + ":" + str(HTTP_SERVER_PORT) + r"/$DIST/" + "\n"
                    ngn_ks_in_new.write(line2)

        if replace_lines and "EOR" not in line:
            ngn_ks_in_new.write(line)

    ngn_ks_in_new.close()

# run lago setup's first two stages : 'init' and 'repo setup'
def create_internal_repo ():
    subprocess.call([r"./run_suite.sh",SUITE])


def start_http_server ():
    return ovirtlago.utils._create_http_server(HTTP_SERVER_ADDR,HTTP_SERVER_PORT,'deployment-ngn_suite_3.6/default/internal_repo')

def install_ngn (http_server):
    _cwd = r"ovirt-node-ng"
    subprocess.call([r"./autogen.sh"],cwd=_cwd)
    subprocess.call(["sudo","make","squashfs"],cwd=_cwd)
    subprocess.call(["sudo","make","installed-squashfs"],cwd=_cwd)
    http_server.shutdown()

    # relace init.json.in to point to an updated json file with the 'local .qcow2' configuration
    subprocess.call(["ln","-s",INIT_SRC,INIT_DST])


def create_ngn_qcow2():
    if (get_file_full_path("ovirt-node-ng",".qcow2") == None):
        replace_lines_in_run_suite()
        add_ngn_function()
        clone_ngn()
        change_kickstart_file()
        create_internal_repo()
        server = start_http_server()
        time.sleep(1)
        install_ngn(server)
        replace_lines_in_run_suite(current_lines = 'run_ngn_suite',new_lines = 'run_suite')


def get_file_full_path(file_directory,uniqe_postfix):
    if os.path.exists(file_directory):
        for file in os.listdir(file_directory):
            if file.endswith(uniqe_postfix):
                return os.path.dirname(os.path.abspath(file_directory + r"/" + file)) + r"/" + file
    return None # didn't find a file


def skip_repo_sync ():
    with open("run_suite.sh") as run_suite:
        data = run_suite.readlines()

    new_file = []
    for line in data:
        new_file.append(line)
        if "$CLI ovirt reposetup" in line:
            new_file.append("\t\t--skip-sync \\\n")

    with open ("run_suite.sh","w") as run_suite2:
        run_suite2.writelines(new_file)

def lago_deployment():
    #skip_repo_sync()
    subprocess.call([r"./run_suite.sh",SUITE])

def main():
    create_ngn_qcow2()
    #lago_deployment()


if __name__ == '__main__':
    main()
