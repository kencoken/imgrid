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
        default=8500
    )
    parser.add_argument(
        '--split_by_subdir',
        help='Split rows by subdir',
        type=bool,
        default=False
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


    grids = []
    images = []

    last_subdir = None

    with open(index_file) as f:
        for line in f:
            line = line.rstrip()
            parts = [x.rstrip() for x in line.split(',')]

            paths = []
            text = None

            if not base_dir:
                abs_path = parts[0]
            else:
                abs_path = os.path.join(base_dir, parts[0])

            if os.path.isdir(abs_path):
                for fname in os.listdir(abs_path):
                    if os.path.splitext(fname)[1].lower() in ['.jpg', '.jpeg', '.png']:
                        paths.append(os.path.join(parts[0], fname))
                paths.append('sep')
            else:
                if not app.config['args'].split_by_subdir:
                    paths.append(parts[0])
                else:
                    this_subdir = os.path.split(parts[0])[0]
                    if this_subdir != last_subdir:
                        if last_subdir is not None:
                            paths.append('sep')
                        last_subdir = this_subdir
                    paths.append(parts[0])

            if len(parts) > 1:
                text = parts[1]

            for path in paths:
                if path != 'sep':
                    if path[0] == os.path.sep:
                        web_path = path[1:]
                    else:
                        web_path = path

                    web_path = os.path.join('static/imgs', web_path)

                    if text is None:
                        fparts = os.path.split(web_path)
                        text_path = os.path.join(os.path.split(fparts[0])[1], fparts[1])
                    else:
                        text_path = text.replace('<fname>', os.path.split(web_path)[1])

                    images.append(dict(
                        href=web_path,
                        text=text_path
                    ))
                else:
                    grids.append(images)
                    images = []
                    # images.append(dict(
                    #     href='static/assets/sep.png',
                    #     text=''
                    # ))

    if len(images) > 0:
        grids.append(images)
    return grids

##

@app.route('/')
def grid():

    grids = read_index_file(app.config['args'].input_index, base_dir=app.config['args'].base_dir)
    from pprint import pprint
    pprint(grids)
    print len(grids[0])
    template = env.get_template('grid.html')
    return template.render(grids=grids,
                           row_height=app.config['args'].row_height)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    args = get_args(parser)
    app.config['args'] = args

    app.run(processes=1,
            host=socket.gethostbyname(socket.gethostname()),
            port=args.srv_port)
