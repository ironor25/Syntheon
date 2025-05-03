// import { useState } from 'react'
import { useRef, useState } from 'react'
import './App.css'
import axios from 'axios'
import { Button } from 'antd'
import LoadingOutlined from '@ant-design/icons/lib/icons/LoadingOutlined'
import SpeechInput from './components/Voice_Input'



function App() {
  const [input,setinput] = useState<string>("")
  const [data,setData]  = useState<string>("")
  const [loading,setloading] = useState(false)
  async function handle_submit(){
    setloading(true)
    try{
    
    const result = await axios.post("http://127.0.0.1:8000/crawl_prompt",{prompt:input})
    console.log(result)
    setData(result.data.answer)
    
    }
    catch{
      console.log("error")
    }
    setloading(false)
  }

  
  return (
    <div className='flex flex-col h-screen w-screen justify-center items-center bg-gray-800'>
      <div className='justify-center'>   
        
     
      <SpeechInput
      inputValue={input}
      setInputValue={setinput}
      />
      <Button className='bg-amber-500 rounded-xl h-8 w-16 m-3'
        onClick={handle_submit}
        >Submit</Button>
        <div className='text-amber-50'>
          {loading ? 
           <LoadingOutlined/>
           :
            data}
      </div> 
    </div>
  </div>
  )
}

export default App
