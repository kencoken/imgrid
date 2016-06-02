from flask import Flask,  redirect, url_for
from jinja2 import Environment, PackageLoader
import argparse
import os
import numpy as np
import socket
from skimage.io import imsave, imread
from skimage.transform import resize


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
        type=int,
        default=120
    )
    parser.add_argument(
        '--page_size',
        help='number of images per page',
        type=int,
        default=200
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
    parser.add_argument(
        '--use_probs',
        help='Use and display part and rr probabilities',
        type=bool,
        default=False
    )
    return parser.parse_args()

def filter_claims(claims, filter_function):
    filtered_claims = []
    for claim in claims:
        if filter_function(claim):
            filtered_claims.append(claim)
    return filtered_claims

def remove_repairs(claim):
    print claim
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
        tmp['text']+=',\n part_score: {},\n rr_score: {}'.format(tmp['part_score'], 
                                                                  tmp['rr_score'])
        new_images.append(tmp)

    return new_images

def get_sorted_grid(grid):
    claim_scores = []
    for item in grid:
        claim_scores.append(item['pooled_prob'])

    order = np.argsort(np.array(claim_scores, dtype=np.float))[::-1]
    new_grid = [grid[i] for i in order]

    return new_grid

def impath_to_thumbpath(path):
    im_name = path.replace('/','_')
    thumb_path = 'static/thumbs/'+im_name[:-4]+'_thumbnail_{}.jpg'.format(app.config['args'].row_height)
    return thumb_path

def create_thumbnails(paths):
    # keep multiple of desired resolution due to crappy resize
    multiple = 2
    if not os.path.exists('static/thumbs'):
        os.mkdir('static/thumbs')
    for path in paths:
        thumb_path = impath_to_thumbpath(path)
        if not os.path.exists(thumb_path):
            img = imread(path)
            aspect_ratio= img.shape[1]*1.0/img.shape[0]
            resized_img = resize(img, (multiple*app.config['args'].row_height, multiple*int(aspect_ratio*app.config['args'].row_height)))
            imsave(thumb_path, resized_img)

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

    last_subdir = None
    prev_meta_label = None
    prev_layman_label = None
    prev_pooled_prob = None

    with open(index_file) as f:
        for line in f:

            paths = []
            line = line.rstrip()
            parts = [x.rstrip() for x in line.split(',')]

            if 'CLAIM_INFO' in line:
                meta_label = parts[2]
                layman_label =  parts[3]
                pooled_prob =  parts[4]
                if prev_meta_label is None:
                    prev_meta_label = meta_label
                    prev_layman_label = layman_label
                    prev_pooled_prob =  pooled_prob
                continue


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

                if app.config['args'].use_probs:
                    part_score = parts[1]
                    rr_score = parts[2]

            # if len(parts) > 1:
                # text = parts[1]

            for path in paths:
                if path != 'sep':
                    if path[0] == os.path.sep:
                        web_path = path[1:]
                    else:
                        web_path = path

                    web_path = os.path.join('static/imgs', web_path)

                    if text is None:
                        fparts = os.path.split(web_path)
                        claim_id = os.path.split(fparts[0])[1]
                        text_path = os.path.join(claim_id, fparts[1])
                    else:
                        text_path = text.replace('<fname>', os.path.split(web_path)[1])

                    images.append(dict(
                            href=web_path,
                            href_thumb=impath_to_thumbpath(web_path),
                            text=text_path
                        ))
                    if not  app.config['args'].split_by_subdir:
                        if len(images) > app.config['args'].page_size:
                            grids.append(dict(images=images))

                    if app.config['args'].use_probs:
                        images[-1]['rr_score'] = rr_score
                        images[-1]['part_score'] = part_score

                else:
                    if app.config['args'].use_probs:
                        images = get_sorted_images(images)

                    grids.append(dict(images=images, claim_id=claim_id))
                    if meta_label is not None:
                        text_string = 'Metadata: {0}'.format(prev_meta_label)
                        text_string += ', Layman: {0}'.format(prev_layman_label)
                        text_string += ', Claim Pooled Prob: {0}'.format(prev_pooled_prob)
                        grids[-1]['pooled_prob'] = prev_pooled_prob
                        grids[-1]['meta_label'] = prev_meta_label
                        grids[-1]['claim_info_text'] = text_string
                        prev_meta_label = meta_label
                        prev_layman_label = layman_label
                        prev_pooled_prob =  pooled_prob

                    images = []
                        # images.append(dict(
                        #     href='static/assets/sep.png',
                        #     text=''
                        # ))

    if len(images) > 0:
        if app.config['args'].use_probs:
            images = get_sorted_images(images)

        grids.append(dict(images=images, claim_id=claim_id))
        if meta_label is not None and app.config['args'].split_by_subdir:
            text_string = 'Metadata: {0}'.format(prev_meta_label)
            text_string += ', Layman: {0}'.format(prev_layman_label)
            text_string += ', Claim Pooled Prob: {0}'.format(prev_pooled_prob)
            grids[-1]['pooled_prob'] = prev_pooled_prob
            grids[-1]['meta_label'] = prev_meta_label
            grids[-1]['claim_info_text'] = text_string
            prev_meta_label = meta_label
            prev_layman_label = layman_label
            prev_pooled_prob =  pooled_prob


    if len(grids)>1:
        if 'pooled_prob' in grids[-1]:
            grids = get_sorted_grid(grids)
    return grids

##

@app.route('/<int:page_id>')
def grid(page_id):
    grids = read_index_file(app.config['args'].input_index, base_dir=app.config['args'].base_dir)
    # from pprint import pprint
    # pprint(grids)
    if app.config['args'].split_by_subdir:
        # assume ~20 images per claim
        page_size = int(app.config['args'].page_size/20.0)
    else:
        page_size = app.config['args'].page_size

    grids = filter_claims(grids, remove_repairs)

    claims_current = grids[page_id*page_size: (page_id+1)*page_size]

    #create_thumbnails
    image_paths = []
    for claim in claims_current:
        for img in claim['images']:
            image_paths.append(img['href'])

    create_thumbnails(image_paths)

    template = env.get_template('grid.html')
    return template.render(grids=claims_current,
                           row_height=app.config['args'].row_height)

@app.route('/')
def home():
    return redirect(url_for('grid', page_id=0))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    args = get_args(parser)
    app.config['args'] = args

    app.run(processes=1,
            host=socket.gethostbyname(socket.gethostname()),
            port=args.srv_port)
