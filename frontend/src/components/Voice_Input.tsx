import React, { useState, useRef } from "react";
import { CloseOutlined, PlusOutlined } from '@ant-design/icons';
import AudioOutlined from '@ant-design/icons/lib/icons/AudioOutlined';
declare global {
  interface Window {
    SpeechRecognition: any;
    webkitSpeechRecognition: any;
  }
}

// Define a custom window type to support webkitSpeechRecognition
type SpeechRecognitionType = typeof window.SpeechRecognition;

interface CustomWindow extends Window {
  webkitSpeechRecognition: SpeechRecognitionType;
  SpeechRecognition: SpeechRecognitionType;
}

interface SpeechInputProps {
  inputValue: string;
  setInputValue: React.Dispatch<React.SetStateAction<string>>;
}

const SpeechInput: React.FC<SpeechInputProps> = ({inputValue,setInputValue}) => {
  const [isListening, setIsListening] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState("");

  const recognitionRef = useRef<any>(null);

  const handleMicClick = () => {
    const SpeechRecognition =
      (window as CustomWindow).SpeechRecognition ||
      (window as CustomWindow).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      alert("Speech Recognition is not supported in this browser.");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.interimResults = true;
    recognition.continuous = true;

    recognition.onresult = (event: any) => {
      let transcript = "";
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        transcript += event.results[i][0].transcript;
      }
      
      // console.log(prev_str)
      setLiveTranscript(transcript);
    };

    recognition.onerror = (e: any) => {
      console.error("Speech recognition error:", e);
      setIsListening(false);
    };

    recognitionRef.current = recognition;
    recognition.start();
    setIsListening(true);
  };

  const handleStopClick = () => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      setIsListening(false);
      setInputValue(liveTranscript);
      setLiveTranscript("");
    }
  };

  return (
    <div 
      className='bg-amber-50 rounded-md border-slate-500 ' 
      style={{ padding: '20px',width: "10in" }}>
    <div className="p-4 mx-auto ">
      <textarea
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        style={{
          width: '9in',
          minHeight: '40px',
          maxHeight: '200px',
          overflowY: 'hidden',
          resize: 'none',  // disable manual dragging
          padding: '10px',
          fontSize: '16px',
          boxSizing: 'border-box',
          marginLeft: "10px"
        
        }}
        onInput={(e) => {
          const target = e.target as HTMLTextAreaElement;
          target.style.height = 'auto'; // reset
          target.style.height = `${Math.min(target.scrollHeight, 200)}px`; // grow until 200px
        }}
        placeholder="Type your message..."
      />
  </div>
  <div className="flex justify-between">
     <button >
              <PlusOutlined
              className='rounded-3xl p-2.5 border-black border-2 ml-7'/>
              </button>
      {!isListening ? (
        <button
          onClick={handleMicClick}
        >
        <AudioOutlined 
            className='border-2 border-black p-2.5 rounded-3xl mr-7'/>
        </button>
      ) : (
        <button
          onClick={handleStopClick}
         
        >
          <CloseOutlined
            className='rounded-3xl p-2.5 border-black border-2 mr-7'/>
        </button>
      )}
  </div>
      {isListening && (
        <div className="mt-3 text-gray-700 italic border-t pt-2">
          📝 <strong>Live:</strong> {liveTranscript}
        </div>
      )}
    </div>
    
  

  );
};

export default SpeechInput;
