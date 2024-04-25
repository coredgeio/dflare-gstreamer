export default class Queue{
    /**
     * @constructor
     * @param {Array}
     */
    constructor(...elements){
      /**
      * @type {Array}
      */
      this.items = [];
      this.enqueue(...elements);
    }
   
    enqueue(...elements){
      elements.forEach(element => this.items.push(element));
    }
   
    dequeue(){
      return this.items.shift();
    }
   
    size(){
      return this.items.length;
    }
   
    isEmpty(){
      return this.items.length===0;
    }
}