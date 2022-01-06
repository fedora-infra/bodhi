import os
import yaml
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))

ROOT_DIR = os.path.realpath(os.path.join(
    SCRIPT_DIR,
    '../../'))

ZUUL_YAML = os.path.realpath(os.path.join(
    SCRIPT_DIR,
    '../../.zuul.yaml'))

def runcmd(command):
    p = subprocess.Popen(command, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT)
    try:
        for line in iter(p.stdout.readline, b''):
            print(line.decode('utf-8'))
        outs, errs = p.communicate(timeout=15)
    except subprocess.TimeoutExpired:
        p.kill()
        outs, errs = p.communicate()
    print(outs)

def main():
    print("Running zuul pods")
    print(ZUUL_YAML)
    project_checks = []
    jobs = {}
    with open(ZUUL_YAML, "r") as stream:
        try:
            zuul_yaml = yaml.safe_load(stream)
            project_checks = [check
                    for item in zuul_yaml if 'project' in item
                    for check in item['project']['check']['jobs']]
            print(project_checks)
            jobs = {item['job']['name']: item['job'] for item in zuul_yaml if 'job' in item}
            print(jobs.keys())
        except yaml.YAMLError as exc:
            print(exc)
    for check in project_checks:
        job = jobs[check]
        nodes = job['nodeset']['nodes']
        label = nodes['label']
        if len(label) > 4 and 'pod-' == label[0:4]:
            name = label[4:]
            dockerfile = os.path.join(SCRIPT_DIR, f"zuul-containers/{name}/Dockerfile")
            runcmd(['podman', 'build', '-f', dockerfile, '-t', nodes['name']])
            
            runcmd(['podman', 'build', '--from', nodes['name'], '-t', nodes['name'] + '-ansible', '-f', dockerfile + '.ansible'])

            runcmd(['podman', 'run', '-v', ROOT_DIR+':/workspace/src:Z',  '-t', nodes['name'] + '-ansible', 'sh', '-c',
             f"ls -la /workspace/src && ansible-playbook -e '{{\"ansible_user_dir\":\"/workspace\", \"zuul\":{{\"project\":{{\"src_dir\":\"src\"}}}}}}' --connection=local --inventory 127.0.0.1, {os.path.join('/workspace/src', job['run'])} "])       
        else:
            print(f"Skipping label {label}")

if __name__ == '__main__':
    main()
