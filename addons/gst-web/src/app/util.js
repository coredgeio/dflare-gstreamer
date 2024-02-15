export default class Queue{
    constructor(...items){
      //initialize the items in queue
      this.items = []
      // enqueuing the items passed to the constructor
      this.enqueue(...items)
    }
   
     enqueue(...items){
       //push items into the queue
       items.forEach( item => this.items.push(item) )
       return this.items;
     }
   
     dequeue(count=1){
       //pull out the first item from the queue
       this.items.splice(0,count);
       return this.items[0];
     }
   
     peek(){
       //peek at the first item from the queue
       return this.items[0]
     }
   
     size(){
       //get the length of queue
       return this.items.length
     }
   
     isEmpty(){
       //find whether the queue is empty or no
       return this.items.length===0
     }
}