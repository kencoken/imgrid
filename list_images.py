import os
import argparse

def get_args(parser):

    parser.add_argument(
        'dir',
        help='Directory to list'
    )
    parser.add_argument(
        'output',
        help='Target index output file'
    )
    parser.add_argument(
        '--exts',
        help='Image exts',
        default='.jpg,.jpeg'
    )
    return parser.parse_args()

def main(opts):

    images = []

    valid_exts = [x.lower() for x in opts['exts'].split(',')]
    for root, dirs, files in os.walk(opts['dir']):
        for file in files:
            if os.path.splitext(file)[1].lower() in valid_exts:
                images.append(os.path.join(root, file))
                
    with open(opts['output'], 'w') as f:
        for line in images:
            f.write('%s\n' % line)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    args = get_args(parser)
    print args
    opts = vars(args)
    main(opts)
