<template>
  <div>
    <input
      type="text"
      placeholder="Search nodes"
      v-model="searchTerm"
      @input="handleInput"
      class="search-box"
    />
  </div>
</template>

<script>
export default {
  props: {
    updateSearch: {
      type: Function,
      required: true,
    },
  },
  data() {
    return {
      searchTerm: "",
    };
  },
  methods: {
    handleInput() {
      this.updateSearch(this.searchTerm);
    },
  },
};
</script>

<style>
.search-box {
  width: 23%;
  padding: 8px;
  margin-bottom: 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
}
</style>
