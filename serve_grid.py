import sys
from flask import Flask,  redirect, url_for
from jinja2 import Environment, PackageLoader
import argparse
import os
import numpy as np
import socket
from PIL import Image
import math

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
        '--images_per_row',
        help='The preferred number of images / row',
        type=int,
        default=6  # should be one of 6, 4, 3
    )
    parser.add_argument(
        '--row_height',
        help='The preferred height in pixels of thumbnail images',
        type=int,
        default=300
    )
    parser.add_argument(
        '--page_size',
        help='number of images per page',
        type=int,
        default=80
    )
    parser.add_argument(
        '--srv_port',
        help='Port on which to launch webserver',
        type=int,
        default=8500
    )
    parser.add_argument(
        '--split_mode',
        help="Split into groups: ['none', 'subdir', 'claim_info_header']",
        default='none'
    )
    parser.add_argument(
        '--use_probs',
        help='Use and display part and rr probabilities',
        type=bool,
        default=False
    )
    parser.add_argument(
        '--space_delim_tokens',
        help='Split N tokens from space delimited input file (if unspecified, by default will split by commas)',
        type=int,
        default=0
    )
    return parser.parse_args()

def filter_claims(claims, filter_function):
    filtered_claims = []
    for claim in claims:
        if filter_function(claim):
            filtered_claims.append(claim)
    return filtered_claims

def remove_repairs(claim):
    if claim['meta_label'] == 'Repair':
        return False
    else:
        return True

def get_sorted_images(images):
    part_scores = []
    for item in images:
        part_scores.append(item['part_score'])

    order = np.argsort(np.array(part_scores, dtype=np.float))[::-1]
    new_images = []
    for i in order:
        tmp = images[i]
        new_images.append(tmp)

    return new_images

def get_sorted_grid(grid):
    grid_scores = []
    for item in grid:
        grid_scores.append(item['pooled_prob'])

    order = np.argsort(np.array(grid_scores, dtype=np.float))[::-1]
    new_grid = [grid[i] for i in order]

    return new_grid

def impath_to_thumbpath(path):
    im_name = path.replace('/', '_')
    thumb_path = 'static/thumbs/%s_thumbnail_%d.jpg' % (os.path.splitext(im_name)[0], app.config['args'].row_height)
    return thumb_path

def create_thumbnails(paths):

    if not os.path.exists('static/thumbs'):
        os.mkdir('static/thumbs')
    for path in paths:
        thumb_path = impath_to_thumbpath(path)
        if not os.path.lexists(thumb_path):
            im = Image.open(path)
            aspect_ratio = im.size[0]*1.0/im.size[1]
            size = [app.config['args'].row_height, int(aspect_ratio*app.config['args'].row_height)]
            im.thumbnail(size, Image.ANTIALIAS)
            im.save(thumb_path)

def read_index_file(index_file, base_dir=None):

    # # create symlink to base_dir
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

    cache=dict(
        grid_id=None,
        last_subdir=None,
        meta_label=None,
        layman_label=None,
        pooled_prob=None
    )

    with open(index_file) as f:
        for line in f:

            paths = []
            line = line.rstrip()
            if app.config['args'].space_delim_tokens < 1:
                parts = [x for x in line.split(',')]
            else:
                token_count = app.config['args'].space_delim_tokens
                all_parts = [x for x in line.split(' ')]
                parts = [' '.join(all_parts[:-token_count])]
                parts.extend(all_parts[-token_count:])

            text = None

            if 'CLAIM_INFO' in line:
                # header line
                if app.config['args'].split_mode == 'claim_info_header':
                    paths.append('sep')

                cache['meta_label'] = parts[2]
                cache['layman_label'] =  parts[3]
                cache['pooled_prob'] =  parts[4]

            else:
                # regular line
                if not base_dir:
                    abs_path = parts[0]
                else:
                    abs_path = os.path.join(base_dir, parts[0])

                if os.path.isdir(abs_path):
                    # line is directory
                    for fname in os.listdir(abs_path):
                        if os.path.splitext(fname)[1].lower() in ['.jpg', '.jpeg', '.png']:
                            paths.append(os.path.join(parts[0], fname))
                    paths.append('sep')
                else:
                    # line is file path
                    if app.config['args'].split_mode in ['none', 'claim_info_header']:
                        paths.append(parts[0])
                    elif app.config['args'].split_mode == 'subdir':
                        this_subdir = os.path.split(parts[0])[0]
                        if this_subdir != cache['last_subdir']:
                            if cache['last_subdir'] is not None:
                                paths.append('sep')
                            cache['last_subdir'] = this_subdir
                        paths.append(parts[0])
                    else:
                        raise RuntimeError('Unknown split mode: %s' % app.config['args'].split_mode)

                    if app.config['args'].use_probs:
                        part_score = float(parts[1])
                        rr_score = float(parts[2])

            # iter over paths (could be multiple if line was directory)
            for path in paths:
                if path != 'sep':
                    if path[0] == os.path.sep:
                        web_path = path[1:]
                    else:
                        web_path = path

                    web_path = os.path.join('static/imgs', web_path)

                    if text is None:
                        fparts = os.path.split(web_path)
                        cache['grid_id'] = os.path.split(fparts[0])[1]
                        text_path = os.path.join(cache['grid_id'], fparts[1])
                    else:
                        text_path = text.replace('<fname>', os.path.split(web_path)[1])

                    image = dict(
                        href=web_path,
                        href_thumb=impath_to_thumbpath(web_path),
                        text=text_path,
                        fname=os.path.split(text_path)[1]
                    )

                    if app.config['args'].use_probs:
                        image.update(dict(
                            rr_score=rr_score,
                            part_score=part_score
                        ))

                    images.append(image)

                else:
                    if app.config['args'].use_probs:
                        images = get_sorted_images(images)

                    grids.append(dict(images=images, grid_id=cache['grid_id']))
                    if cache['meta_label'] is not None:
                        text_string = 'Metadata: {0}'.format(cache['meta_label'])
                        text_string += ', Layman: {0}'.format(cache['layman_label'])
                        text_string += ', Claim Pooled Prob: {0}'.format(cache['pooled_prob'])
                        grids[-1]['pooled_prob'] = cache['pooled_prob']
                        grids[-1]['meta_label'] = cache['meta_label']
                        grids[-1]['info_text'] = text_string

                    images = []

    if len(images) > 0:
        if app.config['args'].use_probs:
            images = get_sorted_images(images)

        grids.append(dict(images=images, grid_id=cache['grid_id']))
        if cache['meta_label'] is not None and app.config['args'].split_mode != 'none':
            text_string = 'Metadata: {0}'.format(cache['meta_label'])
            text_string += ', Layman: {0}'.format(cache['layman_label'])
            text_string += ', Claim Pooled Prob: {0}'.format(cache['pooled_prob'])
            grids[-1]['pooled_prob'] = cache['pooled_prob']
            grids[-1]['meta_label'] = cache['meta_label']
            grids[-1]['info_text'] = text_string

    if len(grids) > 1:
        if 'pooled_prob' in grids[-1]:
            grids = get_sorted_grid(grids)

    return grids

##

@app.route('/<int:page_num>')
def grid(page_num):
    page_id = page_num - 1

    grids = read_index_file(app.config['args'].input_index, base_dir=app.config['args'].base_dir)
    # from pprint import pprint
    # pprint(grids)

    #grids = filter_claims(grids, remove_repairs)

    if app.config['args'].split_mode != 'none':
        # assume ~20 images per claim
        page_size = int(app.config['args'].page_size/20.0)
        page_count = int(math.ceil(float(len(grids)) / float(page_size)))
        claims_current = grids[page_id*page_size:(page_id+1)*page_size]
    else:
        page_size = app.config['args'].page_size
        assert len(grids) == 1
        images = grids[0]['images']
        page_count = int(math.ceil(float(len(images)) / float(page_size)))
        images_current = images[page_id*page_size:(page_id+1)*page_size]
        claims_current = [dict(images=images_current, grid_id='all images')]

    #create_thumbnails
    image_paths = []
    for claim in claims_current:
        for img in claim['images']:
            image_paths.append(img['href'])

    page_image_count = len(image_paths)
    total_image_count = sum([len(x['images']) for x in grids])

    create_thumbnails(image_paths)

    template = env.get_template('grid.html')
    return template.render(grids=claims_current,
                           images_per_row=app.config['args'].images_per_row,
                           row_height=app.config['args'].row_height,
                           page_num=page_num,
                           page_count=page_count,
                           first_grid_id=page_id*page_size,
                           page_image_count=page_image_count,
                           total_image_count=total_image_count)

@app.route('/')
def home():
    return redirect(url_for('grid', page_num=1))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    args = get_args(parser)
    app.config['args'] = args

    app.run(processes=1,
            host=socket.gethostbyname(socket.gethostname()),
            port=args.srv_port)
