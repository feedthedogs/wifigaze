const fs = require('fs')
const { defineConfig } = require('@vue/cli-service')
module.exports = defineConfig({
  transpileDependencies: true,
  devServer: {
    https: false
  },
  configureWebpack: {
    devtool: 'source-map'
  }
})
