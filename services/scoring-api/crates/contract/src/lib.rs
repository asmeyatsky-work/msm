//! # Scoring Contract
//!
//! Generated code from `proto/scoring.proto`. Cross-service wire contract (§1).
//! Imported by presentation to validate request/response shapes; domain types
//! remain separate so the domain is never coupled to protobuf.

#![allow(clippy::all)]
#![allow(unused_qualifications)]

pub mod msm {
    pub mod scoring {
        pub mod v1 {
            include!(concat!(env!("OUT_DIR"), "/msm.scoring.v1.rs"));
        }
    }
}

pub use msm::scoring::v1;
