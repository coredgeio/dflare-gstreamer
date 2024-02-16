export default class Queue{
    constructor(...items){
      this.items = [];
      this.enqueue(...items);
    }
   
    enqueue(...items){
      items.forEach(item => this.items.push(item));
    }
   
    dequeue(count=1){
      return this.items.splice(0, count)[0];
    }
   
    size(){
      return this.items.length;
    }
   
    isEmpty(){
      return this.items.length===0;
    }
}