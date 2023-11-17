const path = require('path')
const HtmlWebpackPlugin = require("html-webpack-plugin");
const { VueLoaderPlugin } = require('vue-loader');

module.exports = {
  target: ["web", "es5"],
  stats: { children: true },
  mode: "development",
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
  module: {
    rules: [
      {
        test: /\.vue$/,
        loader: 'vue-loader',
      },
      {
        test: /\\.js$/,
        loader: "babel-loader",
        exclude: "/node_modules/",
      },
        
        {
          test: /\.css$/,
          use: ['style-loader', 'css-loader'],
        },
    
    ],
  },

  output: {
    path: path.resolve(__dirname, './build'),
    filename: 'bunde.js'
  },
  
  devServer: {
    static: path.resolve(__dirname, "./build"),
    compress: true,
    port: 5501,
    open: true,
  },

  plugins: [
    new HtmlWebpackPlugin({
      template: "./app/index.html",
    }),
    new VueLoaderPlugin()
  ],
  resolve: {
    alias: {
      'vue': 'vue/dist/vue.esm.js',
    },
  },
 
}