const path = require('path');
const glob = require("glob");
const HtmlWebpackPlugin = require('html-webpack-plugin');
const TerserPlugin = require('terser-webpack-plugin');
const MiniCssExtractPlugin = require("mini-css-extract-plugin");
const CssMinimizerPlugin = require("css-minimizer-webpack-plugin");
// const {PurgeCSSPlugin} = require('purgecss-webpack-plugin');

module.exports = {
  target: ["web", "es5"],
  stats: { children: true },
  mode: 'production',
  entry: {
    bundle: [
      path.resolve(__dirname, './app/app.js'),
      path.resolve(__dirname, './app/lib/webrtc-adapter-v7.7.1.js'),
      path.resolve(__dirname, './app/lib/guacamole-keyboard-selkies.js'),
      path.resolve(__dirname, './app/gamepad.js'),
      path.resolve(__dirname, './app/input.js'),
      path.resolve(__dirname, './app/signalling.js'),
      path.resolve(__dirname, './app/webrtc.js'),
    ],
  },
  output: {
    filename: 'app.js',
    path: path.resolve(__dirname, './build')
  },
  module: {
    rules: [
    
      {
        test: /\.js$/,
        loader: 'babel-loader',
        exclude: /node_modules/,
      },
      {
        test: /\.css$/,
        use: [MiniCssExtractPlugin.loader, 'css-loader'],
      },
      {
        test: /\.(woff|woff2|eot|ttf|otf)$/i,
        type: 'asset/resource',
      },
    ],
  },
  plugins: [
    new MiniCssExtractPlugin({
      filename: "style.css"
    }),
  
    new HtmlWebpackPlugin({
      template: './app/index.html',
      filename: 'index.html',
      inject: 'body',
      scriptLoading: 'blocking',
    }),
    // new PurgeCSSPlugin({
    //   paths: glob.sync([
    //     path.join(__dirname, 'app/**/*.js'),
    //     path.join(__dirname, 'app/**/*.html'),
    //   ])
    // }),

   
  ],

  optimization: {
    minimize: true,
    minimizer: [new TerserPlugin(),new CssMinimizerPlugin()],
  },
};
