var gulp = require('gulp');
var postcss = require('gulp-postcss');
var scss = require('gulp-scss');
var watch = require('gulp-watch');
var autoprefixer = require('autoprefixer');

var debug = require('gulp-debug');

function compileScss() {
    var processors = [autoprefixer];
    return gulp.src(['./static/**/*.scss', '!./static/**/_*.scss'])
        .pipe(debug({title: 'debug:'}))
        .pipe(scss())
        .pipe(debug({title: 'debug:'}))
        .pipe(postcss(processors))
        .pipe(gulp.dest('./static'));
}

gulp.task('scss', compileScss);
gulp.task('watch', function() {
    watch('./**/*.scss', compileScss);
});
