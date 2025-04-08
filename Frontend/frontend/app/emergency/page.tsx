'use client'

import { useEffect, useState } from 'react'
import { initializeApp } from 'firebase/app'
import { getDatabase, ref, onValue } from 'firebase/database'
import EmergencyMap from '@/components/emergency/emergency-map'
import CallLog from '@/components/emergency/call-log'
import Transcript from '@/components/emergency/transcript'
import CaseDetails from '@/components/emergency/case-details'

// Your Firebase configuration
const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
  // Add your Realtime Database URL if it's different from the default
  databaseURL: process.env.NEXT_PUBLIC_FIREBASE_DATABASE_URL,
}

// Initialize Firebase
const app = initializeApp(firebaseConfig)
const db = getDatabase(app)

// Add debug logging for Firebase config
console.log('Firebase Project ID:', firebaseConfig.projectId)
console.log('Firebase Auth Domain:', firebaseConfig.authDomain)
console.log('Firebase API Key:', firebaseConfig.apiKey)
console.log('Firebase App ID:', firebaseConfig.appId)
console.log('Firebase Database URL:', firebaseConfig.databaseURL)

interface EmergencyTicket {
  ticket_id: string
  name: string
  location: string
  datetime: string
  status: string
  priority: string
  summary: string
  life_threatening: boolean
  breathing_issue: string
  fire_visibility: string
  smoke_visibility: string
  help_for_whom: string[]
  services_needed: string[]
  ticket_type: string
  transcripts: {
    role?: string
    text: string
  }[]
}

export default function EmergencyDashboard() {
  const [tickets, setTickets] = useState<EmergencyTicket[]>([])
  const [selectedTicket, setSelectedTicket] = useState<EmergencyTicket | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    console.log('Starting to fetch tickets from Realtime Database...')

    try {
      // Reference to the tickets in Realtime Database
      const ticketsRef = ref(db, 'tickets')

      // Subscribe to Realtime Database updates
      const unsubscribe = onValue(ticketsRef, (snapshot) => {
        console.log('onValue called')
        const data = snapshot.val()
        console.log('Received Realtime Database data:', data)

        if (data) {
          const newTickets = Object.keys(data).map(key => {
            const ticketData = data[key]
            return {
              ticket_id: key,
              ...ticketData,
              // Ensure arrays are properly formatted
              help_for_whom: ticketData.help_for_whom || [],
              services_needed: ticketData.services_needed || [],
              transcripts: ticketData.transcripts || [],
            } as EmergencyTicket
          })

          // Sort by datetime descending
          newTickets.sort((a, b) => new Date(b.datetime).getTime() - new Date(a.datetime).getTime())

          setTickets(newTickets)
          setLoading(false)

          // If we have tickets but none selected, select the first one
          if (newTickets.length > 0 && !selectedTicket) {
            setSelectedTicket(newTickets[0])
          }
        } else {
          setTickets([])
          setLoading(false)
        }

        console.log('Data loaded successfully')
      }, (error) => {
        console.error('Realtime Database subscription error:', error)
        setLoading(false)
      })

      return () => unsubscribe()
    } catch (error) {
      console.error('Error setting up Realtime Database listener:', error)
      setLoading(false)
    }
  }, [selectedTicket])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary"></div>
      </div>
    )
  }

  return (
    <main className="min-h-screen bg-background p-4">
      <div className="grid grid-cols-12 gap-4 h-[calc(100vh-2rem)]">
        {/* Call Log */}
        <div className="col-span-3 bg-card rounded-lg overflow-hidden">
          <CallLog
            tickets={tickets}
            selectedTicket={selectedTicket}
            onSelectTicket={setSelectedTicket}
          />
        </div>

        {/* Map */}
        <div className="col-span-6 bg-card rounded-lg overflow-hidden">
          <EmergencyMap selectedTicket={selectedTicket} />
        </div>

        {/* Transcript and Case Details */}
        <div className="col-span-3 space-y-4">
          <div className="bg-card rounded-lg h-96 overflow-hidden">
            <Transcript selectedTicket={selectedTicket} />
          </div>
          <div className="bg-card rounded-lg h-1/2 overflow-hidden">
            <CaseDetails ticket={selectedTicket} />
          </div>
        </div>
      </div>
    </main>
  )
}