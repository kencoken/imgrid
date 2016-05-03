from flask import Flask
from jinja2 import Environment, PackageLoader
import argparse
import os

import socket

app = Flask(__name__)
app.config.from_object(__name__)
app.config.update(dict(
    DEBUG=True
))
env = Environment(loader=PackageLoader('app', 'templates'))

def get_args(parser):

    parser.add_argument(
        'input_index',
        help='Images to display'
    )
    parser.add_argument(
        '--base_dir',
        help='Base directory for all images',
        default=None
    )
    parser.add_argument(
        '--row_height',
        help='The preferred height of rows in pixels',
        default=120
    )
    parser.add_argument(
        '--srv_port',
        help='Port on which to launch webserver',
        type=int,
        default=-8500
    )

    return parser.parse_args()

def read_index_file(index_file, base_dir=None):

    # create symlink to base_dir
    if os.path.exists('static/imgs'):
        os.unlink('static/imgs')

    pwd = os.getcwd()
    os.chdir('static')
    if base_dir:
        os.symlink(base_dir, 'imgs')
    else:
        os.symlink('/', 'imgs')
    os.chdir(pwd)


    images = []

    with open(index_file) as f:
        for line in f:
            if line[0] == os.path.sep:
                line = line[1:]
            line = line.rstrip()

            path = os.path.join('static/imgs', line)
            parts = os.path.split(path)
            text = os.path.join(os.path.split(parts[0])[1], parts[1])
            images.append(dict(
                href=path,
                text=text
            ))

    return images

##

@app.route('/')
def grid():

    images = read_index_file(app.config['args'].input_index, base_dir=app.config['args'].base_dir)
    print images
    template = env.get_template('grid.html')
    return template.render(images=images,
                           row_height=app.config['args'].row_height)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    args = get_args(parser)
    app.config['args'] = args

    app.run(processes=1,
            host=socket.gethostbyname(socket.gethostname()),
            port=8500)
